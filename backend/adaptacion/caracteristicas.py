"""Variables de entrada del modelo, calculadas a partir de una sesión."""

from statistics import mean

from .reglas import ORDEN_NIVELES

NOMBRES = [
    "nivel",             # 0 fácil, 1 medio, 2 difícil
    "tasa_aciertos",     # resueltas al primer intento / total
    "tasa_reintentos",   # resueltas tras uno o más errores / total
    "tasa_agotadas",     # sin resolver tras agotar los intentos / total
    "tiempo_promedio_s",
    "media_reciente",    # tasa de aciertos media de las últimas sesiones
    "sesiones_previas",  # cuántas sesiones previas hay (máximo 3)
]
HISTORIAL = 3
INTENTOS_MAXIMOS = 3


def resultados_por_pregunta(respuestas, intentos_maximos=INTENTOS_MAXIMOS):
    """Clasifica cada pregunta respondida en acierto, reintento o agotada."""
    por_pregunta = {}
    for r in respuestas:
        por_pregunta.setdefault(r.indice_pregunta, []).append(r)
    conteo = {"acierto": 0, "reintento": 0, "agotada": 0}
    for intentos in por_pregunta.values():
        if any(r.correcta and r.intento == 1 for r in intentos):
            conteo["acierto"] += 1
        elif any(r.correcta for r in intentos):
            conteo["reintento"] += 1
        elif len(intentos) >= intentos_maximos:
            conteo["agotada"] += 1
    return conteo


def vector(nivel, total, conteo, tiempo_promedio_s, tasas_previas):
    total = max(total, 1)
    tasa = conteo["acierto"] / total
    previas = list(tasas_previas)[-HISTORIAL:]
    return [
        ORDEN_NIVELES.index(nivel),
        tasa,
        conteo["reintento"] / total,
        conteo["agotada"] / total,
        tiempo_promedio_s if tiempo_promedio_s is not None else 10.0,
        mean(previas) if previas else tasa,
        len(previas),
    ]


def de_sesion(sesion):
    """Vector de una sesión recién terminada (con sus respuestas ya guardadas)."""
    from sesiones.models import EstadoSesion

    anteriores = (
        sesion.paciente.sesiones.filter(estado=EstadoSesion.FINALIZADA, fin__lt=sesion.fin)
        .exclude(pk=sesion.pk)
        .order_by("-fin")[:HISTORIAL]
    )
    tasas = [s.aciertos / s.total_preguntas for s in reversed(anteriores) if s.total_preguntas]
    return vector(
        sesion.nivel,
        sesion.total_preguntas,
        resultados_por_pregunta(sesion.respuestas.all()),
        sesion.tiempo_promedio_s,
        tasas,
    )
