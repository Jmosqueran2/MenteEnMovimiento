"""Reglas fijas de ajuste de dificultad.

Se usan como respaldo cuando el modelo de scikit-learn no está entrenado o
falla, y como límites de seguridad sobre lo que el modelo recomiende.
"""

from pacientes.models import Nivel

ORDEN_NIVELES = [Nivel.FACIL, Nivel.MEDIO, Nivel.DIFICIL]

TASA_PARA_SUBIR = 0.80
TIEMPO_MAXIMO_PARA_SUBIR_S = 6.0
TASA_PARA_BAJAR = 0.50

# Límites de seguridad que el modelo nunca puede saltarse.
TASA_MINIMA_PARA_SUBIR = 0.60
TASA_MINIMA_PARA_NO_BAJAR = 0.85


def ajuste_por_reglas(tasa_aciertos, tiempo_promedio_s):
    """Devuelve -1 (bajar), 0 (mantener) o 1 (subir)."""
    rapido = tiempo_promedio_s is not None and tiempo_promedio_s <= TIEMPO_MAXIMO_PARA_SUBIR_S
    if tasa_aciertos >= TASA_PARA_SUBIR and rapido:
        return 1
    if tasa_aciertos < TASA_PARA_BAJAR:
        return -1
    return 0


def aplicar_limites(ajuste, tasa_aciertos):
    if ajuste > 0 and tasa_aciertos < TASA_MINIMA_PARA_SUBIR:
        return 0
    if ajuste < 0 and tasa_aciertos >= TASA_MINIMA_PARA_NO_BAJAR:
        return 0
    return ajuste


def mover_nivel(nivel_actual, ajuste):
    indice = ORDEN_NIVELES.index(nivel_actual) + ajuste
    return ORDEN_NIVELES[min(max(indice, 0), len(ORDEN_NIVELES) - 1)]


def recomendar_nivel(nivel_actual, tasa_aciertos, tiempo_promedio_s):
    """Compatibilidad: nivel siguiente usando solo las reglas."""
    return mover_nivel(nivel_actual, ajuste_por_reglas(tasa_aciertos, tiempo_promedio_s))
