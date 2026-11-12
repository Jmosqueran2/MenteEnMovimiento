"""Sesión preparada del día: el cuidador la deja lista (pantalla 11) y el
adulto mayor la empieza cuando quiere (pantallas 03–04)."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from pacientes.models import Puntero, TipoActividad

from .models import EstadoSesion, PedidoAyuda, Sesion, SesionPreparada

# Pedidos de ayuda iguales dentro de este lapso cuentan como uno solo.
VENTANA_AYUDA = timedelta(minutes=2)
# Tasa de aciertos para sugerir "Puede iniciar sola" tras una sesión acompañada.
TASA_PARA_AUTONOMIA = 0.75

NOMBRES = dict(TipoActividad.choices)


def actual(paciente):
    """La última sesión preparada de hoy, o None."""
    return paciente.preparadas.filter(fecha=timezone.localdate()).first()


def realizables(actividades, paciente):
    """Coordinación es un ejercicio de movimiento: con "La voz" no se ofrece."""
    return [a for a in actividades
            if not (paciente.puntero == Puntero.VOZ and a == TipoActividad.COORDINACION)]


def _ayuda_pendiente(paciente):
    pedido = paciente.pedidos_ayuda.filter(atendido=False).first()
    if pedido is None:
        return None
    return {"id": pedido.id, "creado": pedido.creado, "motivo": pedido.motivo,
            "motivo_texto": pedido.get_motivo_display()}


def resumen(paciente, prep=None):
    """Estado para la franja del panel (11) y para las pantallas 03, 04 y 08."""
    prep = prep if prep is not None else actual(paciente)
    datos = {
        "estado": "no_preparada",
        "inicio_autonomo": paciente.inicio_autonomo,
        "ayuda": _ayuda_pendiente(paciente),
    }
    if prep is None:
        return datos

    sesiones = list(prep.sesiones.filter(estado=EstadoSesion.FINALIZADA).order_by("fin"))
    hechas = list(dict.fromkeys(s.tipo for s in sesiones))
    posibles = realizables(prep.actividades, paciente)
    aciertos = sum(s.aciertos for s in sesiones)
    total = sum(s.total_preguntas for s in sesiones)
    completa = bool(posibles) and all(t in hechas for t in posibles)

    # Actividades que hizo hace poco y hoy no tocan: se le avisa en la pantalla 03.
    recientes = (Sesion.objects.filter(paciente=paciente, estado=EstadoSesion.FINALIZADA)
                 .exclude(preparada=prep).order_by("-fin").values_list("tipo", flat=True)[:3])
    quitadas = [t for t in dict.fromkeys(recientes) if t not in posibles]

    sin_ayuda = not paciente.pedidos_ayuda.filter(creado__gte=prep.preparada).exists()
    sugerir = (not paciente.inicio_autonomo and prep.estado == "terminada" and completa
               and total > 0 and aciertos / total >= TASA_PARA_AUTONOMIA and sin_ayuda)

    datos.update({
        "id": prep.id,
        "estado": prep.estado,
        "fecha": prep.fecha,
        "actividades": prep.actividades,
        "realizables": posibles,
        "nombres": {t: NOMBRES[t] for t in prep.actividades},
        "hechas": hechas,
        "quitadas": quitadas,
        "nivel": prep.nivel,
        "nivel_texto": prep.get_nivel_display(),
        "preparada": prep.preparada,
        "iniciada": prep.iniciada,
        "terminada": prep.terminada,
        "completa": completa,
        "aciertos": aciertos,
        "total": total,
        "sugerir_autonomia": sugerir,
    })
    return datos


@transaction.atomic
def preparar(paciente):
    """Crea la sesión de hoy con la configuración ya guardada del paciente."""
    prep = actual(paciente)
    if prep and prep.estado == "en_curso":
        raise ValidationError({"detail": f"{paciente.nombre} está haciendo su sesión. "
                                         "Podrás prepararla de nuevo cuando termine."})
    if not paciente.actividades_habilitadas:
        raise ValidationError({"actividades_habilitadas": "Elige al menos una actividad para preparar la sesión."})
    if (TipoActividad.HISTORIA in paciente.actividades_habilitadas
            and not paciente.contenidos.exists()):
        raise ValidationError({"actividades_habilitadas":
                               "Mi Historia no tiene fotos todavía. Sube alguna o quítala de hoy."})
    if not realizables(paciente.actividades_habilitadas, paciente):
        raise ValidationError({"actividades_habilitadas":
                               "Con «La voz» no se puede hacer Coordinación. Elige otra actividad."})
    # Una sesión lista sin empezar se reemplaza; así no quedan dos vigentes.
    if prep and prep.estado == "lista":
        prep.delete()
    return SesionPreparada.objects.create(
        paciente=paciente, actividades=list(paciente.actividades_habilitadas), nivel=paciente.nivel,
    )


def sincronizar(paciente):
    """Si el cuidador guarda cambios con una sesión lista (sin empezar), la sesión los toma."""
    prep = actual(paciente)
    if prep and prep.estado == "lista":
        prep.actividades = list(paciente.actividades_habilitadas)
        prep.nivel = paciente.nivel
        prep.save(update_fields=["actividades", "nivel"])


def comenzar(paciente):
    prep = actual(paciente)
    if prep is None:
        raise ValidationError({"detail": "Aún no hay actividades listas para hoy."})
    if prep.estado == "terminada":
        raise ValidationError({"detail": "La sesión de hoy ya terminó."})
    if prep.iniciada is None:
        prep.iniciada = timezone.now()
        prep.save(update_fields=["iniciada"])
    return prep


def terminar(paciente):
    """La persona sale (despedida) o el cuidador la da por terminada desde el panel."""
    prep = actual(paciente)
    if prep and prep.estado == "en_curso":
        prep.terminada = timezone.now()
        prep.save(update_fields=["terminada"])
    return prep


def vincular(paciente, tipo):
    """Al iniciar una actividad: la asocia a la sesión de hoy y la marca en curso."""
    prep = actual(paciente)
    if prep is None or prep.estado == "terminada":
        return None
    if tipo not in prep.actividades:
        raise ValidationError({"tipo": "Esta actividad no está en la sesión de hoy."})
    if prep.iniciada is None:
        prep.iniciada = timezone.now()
        prep.save(update_fields=["iniciada"])
    return prep


def al_finalizar(sesion):
    """Cuando ya hizo todas las actividades preparadas, la sesión del día termina."""
    prep = sesion.preparada
    if prep is None or prep.terminada:
        return
    if resumen(sesion.paciente, prep)["completa"]:
        prep.terminada = timezone.now()
        prep.save(update_fields=["terminada"])


def pedir_ayuda(paciente, motivo):
    reciente = paciente.pedidos_ayuda.filter(
        atendido=False, motivo=motivo, creado__gte=timezone.now() - VENTANA_AYUDA
    ).first()
    return reciente or PedidoAyuda.objects.create(paciente=paciente, motivo=motivo)


def atender_ayuda(paciente):
    paciente.pedidos_ayuda.filter(atendido=False).update(atendido=True)
