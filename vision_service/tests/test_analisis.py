import math
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


# --- Mirada ------------------------------------------------------------------

def rostro(cabeza=(0.0, 0.0), iris=(0.0, 0.0), escala=1.0, desplazamiento=(0, 0), apertura=0.3):
    """478 puntos sintéticos: solo se rellenan los que usa rasgos_mirada."""
    puntos = [(0.0, 0.0)] * 478
    dx, dy = desplazamiento

    def poner(i, x, y):
        puntos[i] = (dx + x * escala, dy + y * escala)

    for (a, b, sup, inf, centro_iris), cx in zip(analisis.OJOS, (-30, 30)):
        poner(a, cx - 10, 0)
        poner(b, cx + 10, 0)
        poner(sup, cx, -10 * apertura)
        poner(inf, cx, 10 * apertura)
        for i in centro_iris:  # centro + borde: todos en el mismo punto basta
            poner(i, cx + iris[0] * 20, iris[1] * 20)
    poner(analisis.PUNTA_NARIZ, cabeza[0] * 60, 30 + cabeza[1] * 60)
    return puntos


def test_rasgos_mirada_no_dependen_de_la_distancia_ni_la_posicion():
    base = analisis.rasgos_mirada(rostro(cabeza=(0.2, 0.1), iris=(0.15, -0.05)))
    otro = analisis.rasgos_mirada(rostro(cabeza=(0.2, 0.1), iris=(0.15, -0.05),
                                         escala=2.5, desplazamiento=(200, 90)))
    for clave in ("cabeza_x", "cabeza_y", "iris_x", "iris_y"):
        assert otro[clave] == pytest.approx(base[clave])
    assert base["cabeza_x"] == pytest.approx(0.2)
    assert base["iris_x"] == pytest.approx(0.15)
    assert base["ojos_abiertos"] is True


def test_parpadeo():
    assert analisis.rasgos_mirada(rostro(apertura=0.05))["ojos_abiertos"] is False


def test_parpadeo_con_parpados_caidos():
    """Con la apertura habitual medida, un ojo poco abierto pero normal para
    esa persona no cuenta como parpadeo; cerrarlo más sí."""
    habitual = 0.07  # por debajo del umbral fijo
    assert analisis.rasgos_mirada(rostro(apertura=0.07), apertura_habitual=habitual)["ojos_abiertos"] is True
    assert analisis.rasgos_mirada(rostro(apertura=0.02), apertura_habitual=habitual)["ojos_abiertos"] is False


def test_mirada_blendshapes():
    assert analisis.mirada_blendshapes(None) == (0.0, 0.0)
    # Ambos ojos hacia el mismo lado y hacia arriba.
    x, y = analisis.mirada_blendshapes({"eyeLookOutLeft": 0.6, "eyeLookInRight": 0.6,
                                        "eyeLookUpLeft": 0.4, "eyeLookUpRight": 0.4})
    assert x == pytest.approx(0.6)
    assert y == pytest.approx(0.4)


def test_ajuste_mirada_descarta_distracciones():
    """Algunas muestras mirando a otro lado no deben arruinar la calibración."""
    azar = random.Random(5)
    muestras = []
    for px, py in analisis.PUNTOS_CALIBRACION_MIRADA:
        for k in range(12):
            iris = ((px - 0.5) * 0.3, (py - 0.5) * 0.2)
            if k == 0:  # se distrajo: mira a cualquier parte
                iris = (azar.uniform(-0.15, 0.15), azar.uniform(-0.1, 0.1))
            muestras.append((analisis.rasgos_mirada(rostro((0.0, 0.0), iris)), (px, py)))
    modelo, error = analisis.ajustar_mirada(muestras)
    assert error < 0.02


def test_ajuste_mirada_aprende_la_relacion():
    """Persona simulada que mira combinando cabeza e iris, con ruido."""
    azar = random.Random(3)
    muestras = []
    for px, py in analisis.PUNTOS_CALIBRACION_MIRADA:
        for _ in range(12):
            cabeza = ((px - 0.5) * 0.5 + azar.gauss(0, 0.01), (py - 0.5) * 0.4 + azar.gauss(0, 0.01))
            iris = ((px - 0.5) * 0.2 + azar.gauss(0, 0.005), (py - 0.5) * 0.1 + azar.gauss(0, 0.005))
            muestras.append((analisis.rasgos_mirada(rostro(cabeza, iris)), (px, py)))
    modelo, error = analisis.ajustar_mirada(muestras)
    assert error < 0.05

    # Un punto que no se usó al calibrar.
    x, y = modelo.mapear(analisis.rasgos_mirada(rostro((0.3 * 0.5, -0.2 * 0.4), (0.3 * 0.2, -0.2 * 0.1))))
    assert x == pytest.approx(0.8, abs=0.05)
    assert y == pytest.approx(0.3, abs=0.05)


def test_ajuste_mirada_solo_con_los_ojos():
    """Si la cabeza no se mueve, su variable no aporta y el ajuste no explota."""
    muestras = [(analisis.rasgos_mirada(rostro((0.0, 0.0), ((px - 0.5) * 0.3, (py - 0.5) * 0.2))), (px, py))
                for px, py in analisis.PUNTOS_CALIBRACION_MIRADA for _ in range(5)]
    modelo, error = analisis.ajustar_mirada(muestras)
    assert error < 0.02
    assert all(math.isfinite(w) for w in modelo.wx + modelo.wy)


def test_modelo_mirada_desde_dict():
    modelo = analisis.ModeloMirada([0.5, 1.0, 2.0, 0.3], [0.5, 1.0, 2.0, 0.3])
    assert analisis.ModeloMirada.desde_dict(modelo.como_dict()) == modelo
    # Los de la versión anterior (3 pesos) se completan con 0.
    antiguo = analisis.ModeloMirada.desde_dict({"wx": [0.5, 1, 2], "wy": [0.5, 1, 2]})
    assert antiguo.wx == [0.5, 1.0, 2.0, 0.0]
    with pytest.raises(ValueError):
        analisis.ModeloMirada.desde_dict({"wx": [1, 2], "wy": [1, 2, 3]})
    with pytest.raises(ValueError):
        analisis.ModeloMirada.desde_dict({"wx": [1, 2, float("nan")], "wy": [1, 2, 3]})


# --- Movilidad ---------------------------------------------------------------

HOMBROS = ((0.4, 0.6), (0.6, 0.6))  # ancho de hombros 0.2, centrados


def test_movilidad_reducida_pide_menos_alcance():
    completa = analisis.zona_desde_hombros(*HOMBROS, "coordinacion", "completa")
    reducida = analisis.zona_desde_hombros(*HOMBROS, "coordinacion", "reducida")
    assert reducida.x1 - reducida.x0 < completa.x1 - completa.x0
    assert reducida.y0 > completa.y0  # no obliga a subir tanto los brazos


def test_un_brazo_corre_la_zona_hacia_su_lado():
    centro = lambda z: (z.x0 + z.x1) / 2  # noqa: E731
    ambos = analisis.zona_desde_hombros(*HOMBROS, "seleccion", "completa")
    izquierdo = analisis.zona_desde_hombros(*HOMBROS, "seleccion", "brazo_izquierdo")
    derecho = analisis.zona_desde_hombros(*HOMBROS, "seleccion", "brazo_derecho")
    assert centro(izquierdo) < centro(ambos) < centro(derecho)
    # Las etiquetas de los hombros no importan, solo dónde se ven.
    invertido = analisis.zona_desde_hombros(HOMBROS[1], HOMBROS[0], "seleccion", "brazo_derecho")
    assert invertido == derecho


def test_cursor_cabeza():
    neutro = (0.0, 0.5)
    quieto = {"cabeza_x": 0.0, "cabeza_y": 0.5}
    assert analisis.cursor_cabeza(quieto, neutro) == (0.5, 0.5)
    giro = {"cabeza_x": analisis.RANGO_CABEZA_X / 2, "cabeza_y": 0.5 - analisis.RANGO_CABEZA_Y / 2}
    assert analisis.cursor_cabeza(giro, neutro) == pytest.approx((1.0, 0.0))
    muy_lejos = {"cabeza_x": -5.0, "cabeza_y": 5.0}
    assert analisis.cursor_cabeza(muy_lejos, neutro) == (0.0, 1.0)
