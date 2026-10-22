"""Datos sintéticos de entrenamiento.

Todavía no existen sesiones reales suficientes, así que se simulan adultos
mayores con distinta capacidad cognitiva y velocidad motora, y cada sesión se
etiqueta con una política "experta" que mira el desempeño actual, el historial,
los reintentos y la velocidad. El modelo aprende esa política de forma suave y
entrega una probabilidad (confianza) para cada decisión. Con datos reales
etiquetados por un terapeuta se reentrena igual.
"""

import math

import numpy as np

from .caracteristicas import INTENTOS_MAXIMOS, vector
from .reglas import ORDEN_NIVELES

PREGUNTAS = 8
DIFICULTAD = {"facil": 0.25, "medio": 0.5, "dificil": 0.75}
TIEMPO_REFERENCIA_S = {"facil": 6.0, "medio": 7.0, "dificil": 8.0}
RUIDO_ETIQUETA = 0.05  # desacuerdos normales entre terapeutas


def _probabilidad_acierto(capacidad, nivel):
    return 1 / (1 + math.exp(-9 * (capacidad - DIFICULTAD[nivel])))


def _simular_sesion(rng, capacidad, lentitud, nivel):
    p = _probabilidad_acierto(capacidad, nivel)
    conteo = {"acierto": 0, "reintento": 0, "agotada": 0}
    tiempos = []
    for _ in range(PREGUNTAS):
        for intento in range(1, INTENTOS_MAXIMOS + 1):
            # Más difícil = más lento; la pista sube un poco la probabilidad al reintentar.
            tiempos.append(max(1.0, rng.normal(2.5 + 6 * lentitud + 4 * (1 - p), 1.0)))
            if rng.random() < min(p + 0.15 * (intento - 1), 0.98):
                conteo["acierto" if intento == 1 else "reintento"] += 1
                break
        else:
            conteo["agotada"] += 1
    return conteo, float(np.mean(tiempos))


def politica_experta(nivel, conteo, tiempo_promedio_s, tasas_previas):
    """-1 bajar, 0 mantener, 1 subir."""
    tasa = conteo["acierto"] / PREGUNTAS
    reintentos = conteo["reintento"] / PREGUNTAS
    agotadas = conteo["agotada"] / PREGUNTAS
    media = float(np.mean(tasas_previas)) if tasas_previas else tasa
    puntaje = 0.6 * tasa + 0.4 * media
    historial_bueno = not tasas_previas or media >= 0.7

    if puntaje >= 0.8 and tiempo_promedio_s <= TIEMPO_REFERENCIA_S[nivel] and reintentos <= 0.25 and historial_bueno:
        return 1
    if puntaje < 0.5 or (tasa < 0.6 and agotadas >= 0.25):
        return -1
    return 0


def generar(n=6000, semilla=42):
    """Devuelve (X, y) con n sesiones simuladas."""
    rng = np.random.default_rng(semilla)
    X, y = [], []
    for _ in range(n):
        capacidad = rng.uniform(0.05, 0.95)
        lentitud = rng.beta(2, 2)
        nivel = ORDEN_NIVELES[rng.integers(0, 3)]
        previas = []
        for _ in range(rng.integers(0, 4)):
            # El desempeño varía de un día a otro.
            conteo_previo, _ = _simular_sesion(rng, capacidad + rng.normal(0, 0.08), lentitud, nivel)
            previas.append(conteo_previo["acierto"] / PREGUNTAS)
        conteo, tiempo = _simular_sesion(rng, capacidad, lentitud, nivel)

        etiqueta = politica_experta(nivel, conteo, tiempo, previas)
        if rng.random() < RUIDO_ETIQUETA:
            etiqueta = int(rng.choice([e for e in (-1, 0, 1) if e != etiqueta]))
        X.append(vector(nivel, PREGUNTAS, conteo, tiempo, previas))
        y.append(etiqueta)
    return np.array(X), np.array(y)
