import random
import statistics

import numpy as np
import pytest

from app import analisis
from app.filtros import FiltroOneEuro


def mano(extendidos=(), pinza=False):
    """21 puntos sintéticos en píxeles: muñeca abajo y dedos hacia arriba."""
    puntos = [(0, 100), (-15, 85), (-30, 70), (-40, 60), (-50, 50)]  # muñeca + pulgar
    for nombre, x in zip(["indice", "medio", "anular", "menique"], [-15, 0, 15, 30]):
        if nombre in extendidos:
            puntos += [(x, 60), (x, 40), (x, 25), (x, 10)]
        else:
            puntos += [(x, 60), (x, 40), (x, 50), (x, 65)]
    if pinza:
        indice = puntos[8]
        puntos[4] = (indice[0] + 2, indice[1] + 2)
    return puntos


TODOS = ("indice", "medio", "anular", "menique")


def test_gestos():
    assert analisis.clasificar_gesto(mano(TODOS)) == "abierta"
    assert analisis.clasificar_gesto(mano()) == "cerrada"
    assert analisis.clasificar_gesto(mano(["indice"])) == "apunta"
    assert analisis.clasificar_gesto(mano(["indice"], pinza=True)) == "pinza"


def test_luz():
    assert analisis.medir_luz(np.zeros((240, 320), np.uint8))["estado"] == "baja"
    assert analisis.medir_luz(np.full((240, 320), 128, np.uint8))["estado"] == "ok"
    contraluz = np.full((240, 320), 40, np.uint8)
    contraluz[:, :180] = 255
    assert analisis.medir_luz(contraluz)["estado"] == "contraluz"


def test_zona_activa_recorta_a_la_pantalla():
    zona = analisis.ZonaActiva(0.2, 0.8, 0.2, 0.8)
    assert zona.mapear(0.5, 0.5) == pytest.approx((0.5, 0.5))
    assert zona.mapear(0.0, 1.0) == (0.0, 1.0)


def test_coordinacion_exige_estirar_mas():
    hombros = ((0.4, 0.5), (0.6, 0.5))
    seleccion = analisis.zona_desde_hombros(*hombros, "seleccion")
    coordinacion = analisis.zona_desde_hombros(*hombros, "coordinacion")
    assert coordinacion.x1 - coordinacion.x0 > seleccion.x1 - seleccion.x0


def test_angulo():
    assert round(analisis.angulo((0, 0), (1, 0), (2, 0))) == 180
    assert round(analisis.angulo((0, 1), (0, 0), (1, 0))) == 90


def postura_sintetica(confianza=0.9):
    puntos = [[0, 0, 0.0] for _ in range(17)]
    puntos[0] = [320, 120, confianza]   # nariz
    puntos[1] = [310, 110, confianza]   # ojo
    puntos[5] = [200, 200, confianza]   # hombro izquierdo
    puntos[6] = [440, 200, confianza]   # hombro derecho
    puntos[7] = [100, 200, confianza]   # codo izquierdo: brazo estirado al lado
    puntos[9] = [0, 200, confianza]
    puntos[8] = [460, 300, confianza]   # codo derecho doblado
    puntos[10] = [440, 200, confianza]
    return puntos


def test_postura():
    postura = analisis.analizar_postura(postura_sintetica(), 640, 480)
    assert postura["rostro_visible"] and postura["centrado"]
    assert postura["distancia"] == "ok"
    assert postura["brazos"]["izquierdo"]["extendido"] is True
    assert postura["brazos"]["derecho"]["extendido"] is False
    assert analisis.alertas({"estado": "ok"}, postura) == []


def test_alertas():
    assert analisis.alertas({"estado": "baja"}, {"persona": False}) == ["poca_luz", "sin_persona"]


def test_filtro_reduce_temblor():
    random.seed(1)
    filtro = FiltroOneEuro()
    entrada = [0.5 + random.uniform(-0.02, 0.02) for _ in range(60)]
    salida = [filtro(x, i / 15) for i, x in enumerate(entrada)]
    assert statistics.pstdev(salida[10:]) < statistics.pstdev(entrada[10:]) / 2
