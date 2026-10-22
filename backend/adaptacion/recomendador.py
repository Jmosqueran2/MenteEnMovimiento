import logging

from . import caracteristicas, modelo
from .reglas import ajuste_por_reglas, aplicar_limites, mover_nivel

log = logging.getLogger(__name__)
TEXTO = {-1: "bajar", 0: "mantener", 1: "subir"}


def recomendar(sesion):
    """Decide el nivel de la próxima sesión.

    Usa el modelo de scikit-learn si está entrenado; si no, o si falla, las
    reglas fijas. En ambos casos se aplican límites de seguridad y nunca se
    salta más de un nivel.
    """
    tasa = sesion.aciertos / sesion.total_preguntas
    resultado = None
    try:
        resultado = modelo.predecir(caracteristicas.de_sesion(sesion))
    except Exception:
        log.exception("Falló el modelo de dificultad; se usan las reglas.")

    if resultado is None:
        ajuste, confianza, metodo = ajuste_por_reglas(tasa, sesion.tiempo_promedio_s), None, "reglas"
    else:
        (ajuste, confianza), metodo = resultado, "modelo"

    ajuste = aplicar_limites(ajuste, tasa)
    return {
        "ajuste": TEXTO[ajuste],
        "confianza": round(confianza, 3) if confianza is not None else None,
        "metodo": metodo,
        "nivel_siguiente": mover_nivel(sesion.paciente.nivel, ajuste),
    }
