"""Lógica de las sesiones de estimulación: armar preguntas, registrar
respuestas, cerrar la sesión y calcular el seguimiento."""

from datetime import timedelta
from statistics import mean

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from historia.models import ContenidoHistoria

from adaptacion.recomendador import recomendar
from . import juegos
from .models import EstadoSesion, Respuesta, Sesion

MAX_INTENTOS = 3


# --- Armado del plan (los juegos están en juegos.py) -------------------------

def iniciar_sesion(paciente, tipo):
    if tipo not in paciente.actividades_habilitadas:
        raise ValidationError({"tipo": "Esta actividad está deshabilitada por tu cuidador."})
    plan = juegos.armar_plan(paciente, tipo)
    return Sesion.objects.create(paciente=paciente, tipo=tipo, nivel=paciente.nivel, plan=plan)


def _opcion_publica(opcion, contenidos):
    publica = {k: v for k, v in opcion.items() if k != "contenido_id"}
    contenido = contenidos.get(opcion.get("contenido_id"))
    if contenido is not None:
        publica["imagen"] = contenido.archivo.url
    return publica


def preguntas_publicas(sesion):
    """El plan sin la respuesta correcta ni la pista, que se revelan al responder.
    (En Parejas las cartas tienen que viajar al navegador para poder destaparlas.)"""
    ids = set()
    for item in sesion.plan:
        ids.add(item.get("contenido_id"))
        ids.update(op.get("contenido_id") for op in item["opciones"])
    ids.discard(None)
    contenidos = ContenidoHistoria.objects.in_bulk(list(ids))
    preguntas = []
    for indice, item in enumerate(sesion.plan):
        pregunta = {
            "indice": indice,
            # Las sesiones anteriores a los juegos nuevos no tienen estos campos.
            "juego": item.get("juego", "eleccion"),
            "modo": item.get("modo", "eleccion"),
            "ajustes": item.get("ajustes", {}),
            "enunciado": item["enunciado"],
            "estimulo": item["estimulo"],
            "opciones": [_opcion_publica(op, contenidos) for op in item["opciones"]],
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


def _texto(opciones, indices):
    return {"texto": " → ".join(opciones[i]["texto"] for i in indices), "emoji": ""}


def _evaluar(item, opcion, orden, errores):
    """Devuelve (correcta, opción guardada, lo que eligió, respuesta correcta,
    cuántas jugadas hubo) según el modo del ítem."""
    opciones = item["opciones"]
    modo = item.get("modo", "eleccion")
    if modo == "orden":
        if orden is None or sorted(orden) != list(range(len(opciones))):
            raise ValidationError({"orden": "Hay que señalar cada paso una sola vez."})
        return (orden == item["correcta"], orden[0], _texto(opciones, orden),
                _texto(opciones, item["correcta"]), len(opciones))
    if modo == "parejas":
        if errores is None:
            raise ValidationError({"errores": "Falta cuántos errores hubo."})
        pares = len(opciones) // 2
        texto = f"Encontraste las {pares} parejas"
        return (errores <= item["ajustes"]["permitido"], min(errores, 32767), {"texto": texto, "emoji": "🃏"},
                {"texto": texto, "emoji": "🃏"}, pares + errores)
    if opcion is None:
        raise ValidationError({"opcion": "Falta la opción elegida."})
    if not 0 <= opcion < len(opciones):
        raise ValidationError({"opcion": "La opción no existe."})
    return (opcion == item["correcta"], opcion, opciones[opcion], opciones[item["correcta"]], 1)


@transaction.atomic
def registrar_respuesta(sesion, indice, tiempo_ms, opcion=None, orden=None, errores=None):
    sesion = Sesion.objects.select_for_update().get(pk=sesion.pk)
    if sesion.estado != EstadoSesion.EN_CURSO:
        raise ValidationError({"detail": "Esta sesión ya terminó."})
    if not 0 <= indice < len(sesion.plan):
        raise ValidationError({"indice_pregunta": "La pregunta no existe en esta sesión."})
    item = sesion.plan[indice]
    correcta, guardada, elegida, solucion, jugadas = _evaluar(item, opcion, orden, errores)
    parejas = item.get("modo") == "parejas"

    previas = sesion.respuestas.filter(indice_pregunta=indice)
    if previas.filter(correcta=True).exists() or (parejas and previas.exists()):
        raise ValidationError({"indice_pregunta": "Esta pregunta ya se respondió bien."})
    intento = previas.count() + 1
    if intento > MAX_INTENTOS:
        raise ValidationError({"indice_pregunta": "Ya no quedan intentos para esta pregunta."})

    if parejas:
        # Parejas siempre termina resuelta: dentro de los errores tolerados es un
        # acierto; con más, cuenta como resuelta con ayuda (como un reintento).
        intento = 1 if correcta else 2
        correcta_guardada = True
    else:
        correcta_guardada = correcta
    Respuesta.objects.create(
        sesion=sesion,
        indice_pregunta=indice,
        opcion_elegida=guardada,
        correcta=correcta_guardada,
        intento=intento,
        # Tiempo por jugada: una partida de parejas o una secuencia larga no
        # debe parecer lentitud para el modelo de dificultad.
        tiempo_ms=round(tiempo_ms / jugadas),
    )

    # Las opciones con foto de Mi Historia vuelven con su URL, como en la pregunta.
    ids = [op.get("contenido_id") for op in (elegida, solucion) if op.get("contenido_id")]
    contenidos = ContenidoHistoria.objects.in_bulk(ids)
    elegida, solucion = _opcion_publica(elegida, contenidos), _opcion_publica(solucion, contenidos)
    resultado = {
        "correcta": correcta,
        "intento": intento,
        "opcion_elegida": elegida,
        "puede_reintentar": not parejas and not correcta and intento < MAX_INTENTOS,
        "progreso": progreso(sesion),
    }
    if parejas:
        resultado["completado"] = True
    if correcta or parejas or intento >= MAX_INTENTOS:
        resultado["respuesta_correcta"] = solucion
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
