"""Lógica de las sesiones de estimulación: armar preguntas, registrar
respuestas, cerrar la sesión y calcular el seguimiento."""

import random
from datetime import timedelta
from statistics import mean

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from actividades.models import Pregunta
from historia.models import ContenidoHistoria, TipoContenido
from pacientes.models import TipoActividad

from adaptacion.recomendador import recomendar
from .models import EstadoSesion, Respuesta, Sesion

PREGUNTAS_POR_SESION = 8
MAX_INTENTOS = 3
MIN_CONTENIDOS_HISTORIA = 2


# --- Armado del plan ---------------------------------------------------------

def _barajar(opciones, correcta):
    orden = list(range(len(opciones)))
    random.shuffle(orden)
    return [opciones[i] for i in orden], orden.index(correcta)


def _plan_de_banco(paciente, tipo):
    preguntas = list(Pregunta.objects.filter(tipo=tipo, nivel=paciente.nivel, activa=True))
    random.shuffle(preguntas)
    if len(preguntas) < PREGUNTAS_POR_SESION:
        otras = list(
            Pregunta.objects.filter(tipo=tipo, activa=True).exclude(nivel=paciente.nivel)
        )
        random.shuffle(otras)
        preguntas += otras
    if not preguntas:
        raise ValidationError({"tipo": "Todavía no hay preguntas cargadas para esta actividad."})

    plan = []
    for pregunta in preguntas[:PREGUNTAS_POR_SESION]:
        opciones, correcta = _barajar(pregunta.opciones, pregunta.respuesta_correcta)
        plan.append(
            {
                "pregunta_id": pregunta.pk,
                "enunciado": pregunta.enunciado,
                "estimulo": {"texto": pregunta.estimulo_texto, "emoji": pregunta.estimulo_emoji},
                "opciones": opciones,
                "correcta": correcta,
                "pista": pregunta.pista,
            }
        )
    return plan


def _plan_de_historia(paciente):
    contenidos = list(paciente.contenidos.all())
    if len(contenidos) < MIN_CONTENIDOS_HISTORIA:
        raise ValidationError(
            {"tipo": "Mi Historia necesita al menos 2 fotos o audios. "
                     "Pide a tu cuidador que los agregue."}
        )
    random.shuffle(contenidos)

    plan = []
    for contenido in contenidos[:PREGUNTAS_POR_SESION]:
        otros = [c for c in contenidos if c.pk != contenido.pk]
        distractores = random.sample(otros, min(3, len(otros)))
        opciones = [{"texto": c.titulo, "emoji": ""} for c in [contenido, *distractores]]
        opciones, correcta = _barajar(opciones, 0)
        plan.append(
            {
                "contenido_id": contenido.pk,
                "enunciado": "¿Qué momento es este?"
                if contenido.tipo == TipoContenido.IMAGEN
                else "Escucha con atención. ¿Qué es?",
                "estimulo": {"texto": "", "emoji": ""},
                "opciones": opciones,
                "correcta": correcta,
                "pista": contenido.pista or "Tómate tu tiempo y recuerda.",
            }
        )
    return plan


def iniciar_sesion(paciente, tipo):
    if tipo not in paciente.actividades_habilitadas:
        raise ValidationError({"tipo": "Esta actividad está deshabilitada por tu cuidador."})
    plan = _plan_de_historia(paciente) if tipo == TipoActividad.HISTORIA \
        else _plan_de_banco(paciente, tipo)
    return Sesion.objects.create(paciente=paciente, tipo=tipo, nivel=paciente.nivel, plan=plan)


def preguntas_publicas(sesion):
    """El plan sin la respuesta correcta ni la pista, que se revelan al responder."""
    ids = [item["contenido_id"] for item in sesion.plan if "contenido_id" in item]
    contenidos = ContenidoHistoria.objects.in_bulk(ids)
    preguntas = []
    for indice, item in enumerate(sesion.plan):
        pregunta = {
            "indice": indice,
            "enunciado": item["enunciado"],
            "estimulo": item["estimulo"],
            "opciones": item["opciones"],
            "medio": None,
        }
        contenido = contenidos.get(item.get("contenido_id"))
        if contenido is not None:
            # La URL prefirmada de S3 se genera al momento, por eso no se guarda en el plan.
            pregunta["medio"] = {"tipo": contenido.tipo, "url": contenido.archivo.url}
        preguntas.append(pregunta)
    return preguntas


# --- Respuestas y cierre -----------------------------------------------------

def _metricas(sesion):
    respuestas = list(sesion.respuestas.all())
    aciertos = sum(1 for r in respuestas if r.correcta and r.intento == 1)
    respondidas = len({r.indice_pregunta for r in respuestas})
    tiempos = [r.tiempo_ms for r in respuestas]
    return {
        "aciertos": aciertos,
        "respondidas": respondidas,
        "total": len(sesion.plan),
        "tiempo_promedio_ms": round(mean(tiempos)) if tiempos else None,
    }


def progreso(sesion):
    metricas = _metricas(sesion)
    return {k: metricas[k] for k in ("aciertos", "respondidas", "total")}


@transaction.atomic
def registrar_respuesta(sesion, indice, opcion, tiempo_ms):
    sesion = Sesion.objects.select_for_update().get(pk=sesion.pk)
    if sesion.estado != EstadoSesion.EN_CURSO:
        raise ValidationError({"detail": "Esta sesión ya terminó."})
    if not 0 <= indice < len(sesion.plan):
        raise ValidationError({"indice_pregunta": "La pregunta no existe en esta sesión."})
    item = sesion.plan[indice]
    if not 0 <= opcion < len(item["opciones"]):
        raise ValidationError({"opcion": "La opción no existe."})

    previas = sesion.respuestas.filter(indice_pregunta=indice)
    if previas.filter(correcta=True).exists():
        raise ValidationError({"indice_pregunta": "Esta pregunta ya se respondió bien."})
    intento = previas.count() + 1
    if intento > MAX_INTENTOS:
        raise ValidationError({"indice_pregunta": "Ya no quedan intentos para esta pregunta."})

    correcta = opcion == item["correcta"]
    Respuesta.objects.create(
        sesion=sesion,
        indice_pregunta=indice,
        opcion_elegida=opcion,
        correcta=correcta,
        intento=intento,
        tiempo_ms=tiempo_ms,
    )

    resultado = {
        "correcta": correcta,
        "intento": intento,
        "opcion_elegida": item["opciones"][opcion],
        "puede_reintentar": not correcta and intento < MAX_INTENTOS,
        "progreso": progreso(sesion),
    }
    if correcta or intento >= MAX_INTENTOS:
        resultado["respuesta_correcta"] = item["opciones"][item["correcta"]]
    if not correcta:
        resultado["pista"] = item["pista"]
    return resultado


@transaction.atomic
def finalizar_sesion(sesion, cancelada=False):
    sesion = Sesion.objects.select_for_update().select_related("paciente").get(pk=sesion.pk)
    if sesion.estado != EstadoSesion.EN_CURSO:
        raise ValidationError({"detail": "Esta sesión ya terminó."})

    metricas = _metricas(sesion)
    sesion.fin = timezone.now()
    sesion.estado = EstadoSesion.CANCELADA if cancelada else EstadoSesion.FINALIZADA
    sesion.total_preguntas = metricas["respondidas"] if cancelada else metricas["total"]
    sesion.aciertos = metricas["aciertos"]
    sesion.tiempo_promedio_ms = metricas["tiempo_promedio_ms"]

    paciente = sesion.paciente
    nivel_anterior = paciente.nivel
    decision = None
    if not cancelada and sesion.total_preguntas:
        decision = recomendar(sesion)
        sesion.nivel_siguiente = decision["nivel_siguiente"]
        sesion.ajuste = decision["ajuste"]
        sesion.ajuste_metodo = decision["metodo"]
        sesion.ajuste_confianza = decision["confianza"]
        paciente.nivel = sesion.nivel_siguiente
        paciente.save(update_fields=["nivel", "actualizado"])
    sesion.save()

    return {
        "estado": sesion.estado,
        "aciertos": sesion.aciertos,
        "total": sesion.total_preguntas,
        "tiempo_promedio_s": sesion.tiempo_promedio_s,
        "duracion_min": sesion.duracion_min,
        "nivel_anterior": nivel_anterior,
        "nivel_siguiente": paciente.nivel,
        "nivel_siguiente_texto": paciente.get_nivel_display(),
        "cambio_nivel": paciente.nivel != nivel_anterior,
        "ajuste": decision,
    }


# --- Seguimiento -------------------------------------------------------------

def sesiones_finalizadas(paciente, dias):
    desde = timezone.now() - timedelta(days=dias)
    return paciente.sesiones.filter(estado=EstadoSesion.FINALIZADA, fin__gte=desde).order_by("fin")


def calcular_seguimiento(paciente, dias=7):
    sesiones = list(sesiones_finalizadas(paciente, dias))
    total_preguntas = sum(s.total_preguntas for s in sesiones)
    total_aciertos = sum(s.aciertos for s in sesiones)
    tiempos = [s.tiempo_promedio_ms for s in sesiones if s.tiempo_promedio_ms is not None]

    return {
        "dias": dias,
        "sesiones": len(sesiones),
        "tasa_aciertos": round(100 * total_aciertos / total_preguntas) if total_preguntas else None,
        "tiempo_promedio_s": round(mean(tiempos) / 1000, 1) if tiempos else None,
        "nivel": paciente.nivel,
        "nivel_texto": paciente.get_nivel_display(),
        "por_sesion": [
            {"etiqueta": f"S{numero}", "fecha": s.fin, "porcentaje": s.tasa_aciertos}
            for numero, s in enumerate(sesiones[-10:], start=1)
        ],
        "recientes": [
            {
                "fecha": s.fin,
                "actividad": s.get_tipo_display(),
                "aciertos": s.aciertos,
                "total": s.total_preguntas,
            }
            for s in reversed(sesiones[-5:])
        ],
    }
