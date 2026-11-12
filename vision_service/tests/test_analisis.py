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


def test_sensibilidad_achica_la_zona_alrededor_del_centro():
    zona = analisis.ZonaActiva(0.2, 0.8, 0.2, 0.8)
    assert zona.escalada(1) is zona
    doble = zona.escalada(2)
    assert doble.mapear(0.5, 0.5) == pytest.approx((0.5, 0.5))
    # Con el doble de sensibilidad, un cuarto del ancho ya llega al borde.
    assert doble.mapear(0.35, 0.65) == pytest.approx((0.0, 1.0))
    assert zona.mapear(0.35, 0.65) == pytest.approx((0.25, 0.75))


def test_sensibilidad_se_limita():
    assert analisis.limitar_sensibilidad(10) == analisis.SENSIBILIDAD_MAXIMA
    assert analisis.limitar_sensibilidad(0.2) == analisis.SENSIBILIDAD_MINIMA
    assert analisis.limitar_sensibilidad("x") == analisis.SENSIBILIDAD_MINIMA
    assert analisis.limitar_sensibilidad(float("nan")) == analisis.SENSIBILIDAD_MINIMA
    assert analisis.limitar_sensibilidad("1.5") == 1.5


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


def sentada(baja_cabeza=0.0, inclina_grados=0.0, mano_arriba=False):
    """Persona sentada de frente: hombros de 240 px y la nariz 120 px por encima."""
    puntos = [[0, 0, 0.0] for _ in range(17)]
    mitad = 120 * math.cos(math.radians(inclina_grados))
    alto = 120 * math.sin(math.radians(inclina_grados))
    puntos[5] = [320 - mitad, 300 - alto, 0.9]
    puntos[6] = [320 + mitad, 300 + alto, 0.9]
    puntos[0] = [320, 180 + baja_cabeza, 0.9]
    puntos[1] = [310, 170 + baja_cabeza, 0.9]
    for codo, muneca, x in ((7, 9, 200), (8, 10, 440)):
        puntos[codo] = [x, 400, 0.9]
        puntos[muneca] = [x, 470, 0.9]  # brazos abajo
    if mano_arriba:
        puntos[10] = [460, 320, 0.9]  # apuntando con la mano derecha
    return analisis.analizar_postura(puntos, 640, 480)["medidas"]


def test_medidas_postura():
    m = sentada()
    assert m["altura_cabeza"] == pytest.approx(0.5)
    assert m["inclinacion_hombros"] == pytest.approx(0.0)
    assert m["brazo_activo"] is False
    assert sentada(inclina_grados=15)["inclinacion_hombros"] == pytest.approx(15)
    assert sentada(mano_arriba=True)["brazo_activo"] is True


def monitor_con_referencia():
    monitor = analisis.MonitorPostura()
    t = 0.0
    for _ in range(analisis.MonitorPostura.MUESTRAS_REFERENCIA):
        assert monitor.actualizar(sentada(), t) in ("midiendo", "buena")
        t += 0.1
    assert monitor.estado == "buena"
    return monitor, t


def test_monitor_postura_avisa_si_se_encorva_un_rato():
    monitor, t = monitor_con_referencia()
    # Bajar la cabeza un momento (mirar abajo de la pantalla) no avisa.
    for _ in range(20):
        t += 0.1
        assert monitor.actualizar(sentada(baja_cabeza=50), t) == "buena"
    monitor.actualizar(sentada(), t + 0.1)
    # Encorvada más de 4 s seguidos: avisa.
    t += 0.2
    for _ in range(45):
        t += 0.1
        estado = monitor.actualizar(sentada(baja_cabeza=50), t)
    assert estado == "encorvado"
    # Se endereza un poco pero no lo suficiente: el aviso sigue.
    t += 2
    assert monitor.actualizar(sentada(baja_cabeza=25), t) == "encorvado"
    # Se endereza de verdad: el aviso se va al cabo de 1 s.
    for _ in range(12):
        t += 0.1
        estado = monitor.actualizar(sentada(), t)
    assert estado == "buena"


def test_monitor_postura_avisa_si_empieza_encorvada():
    """Si se sienta curvada desde el principio, esa no queda como su postura normal."""
    monitor = analisis.MonitorPostura()
    t = 0.0
    for _ in range(analisis.MonitorPostura.MUESTRAS_REFERENCIA + 35):
        t += 0.1
        estado = monitor.actualizar(sentada(baja_cabeza=50), t)  # altura 0,29
    assert estado == "encorvado"
    # Al enderezarse, el aviso se va.
    for _ in range(12):
        t += 0.1
        estado = monitor.actualizar(sentada(), t)
    assert estado == "buena"


def test_monitor_postura_hombros_inclinados():
    monitor, t = monitor_con_referencia()
    for _ in range(45):
        t += 0.1
        estado = monitor.actualizar(sentada(inclina_grados=18), t)
    assert estado == "inclinado"


def test_monitor_postura_ignora_hombros_al_apuntar_con_la_mano():
    monitor, t = monitor_con_referencia()
    for _ in range(60):
        t += 0.1
        estado = monitor.actualizar(sentada(inclina_grados=18, mano_arriba=True), t)
    assert estado == "buena"


def test_monitor_postura_sin_hombros_no_cambia():
    monitor, t = monitor_con_referencia()
    assert monitor.actualizar(None, t + 10) == "buena"
    monitor.pausar()
    assert monitor.estado == "buena"


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


def girar_rostro(puntos, angulo):
    c, s = math.cos(angulo), math.sin(angulo)
    return [(c * x - s * y, s * x + c * y) for x, y in puntos]


def test_rasgos_mirada_no_dependen_de_ladear_la_cabeza():
    """Con la cabeza ladeada, mirar a un lado no debe leerse como mirar arriba."""
    base = analisis.rasgos_mirada(rostro(cabeza=(0.2, 0.1), iris=(0.15, -0.05)))
    ladeada = analisis.rasgos_mirada(girar_rostro(rostro(cabeza=(0.2, 0.1), iris=(0.15, -0.05)), 0.25))
    for clave in ("cabeza_x", "cabeza_y", "iris_x", "iris_y"):
        assert ladeada[clave] == pytest.approx(base[clave], abs=1e-9)
    assert ladeada["inclinacion"] == pytest.approx(0.25)


def test_ajuste_mirada_elige_modelo_cruzado_si_hace_falta():
    """Cámara encima de la pantalla: mirar a un lado también mueve el iris en
    vertical. El modelo por eje no puede separarlo; el cruzado sí."""
    azar = random.Random(7)
    muestras = []
    for px, py in analisis.PUNTOS_CALIBRACION_MIRADA:
        for _ in range(10):
            iris = ((px - 0.5) * 0.3 + azar.gauss(0, 0.002),
                    (py - 0.5) * 0.1 + (px - 0.5) * 0.12 + azar.gauss(0, 0.002))
            muestras.append((analisis.rasgos_mirada(rostro((0.0, 0.0), iris)), (px, py)))
    modelo, error = analisis.ajustar_mirada(muestras)
    assert "iris_x" in modelo.vy  # usa el iris horizontal para estimar la altura
    assert error < 0.03
    x, y = modelo.mapear(analisis.rasgos_mirada(rostro((0.0, 0.0), (0.3 * 0.3, -0.2 * 0.1 + 0.3 * 0.12))))
    assert (x, y) == pytest.approx((0.8, 0.3), abs=0.03)


def test_ajuste_mirada_simple_si_alcanza():
    """Si el modelo por eje ya explica todo, no se elige uno más complejo."""
    muestras = [(analisis.rasgos_mirada(rostro(((px - 0.5) * 0.2, (py - 0.5) * 0.15),
                                               ((px - 0.5) * 0.3, (py - 0.5) * 0.2))), (px, py))
                for px, py in analisis.PUNTOS_CALIBRACION_MIRADA for _ in range(4)]
    modelo, _ = analisis.ajustar_mirada(muestras)
    assert modelo.vx == analisis.VARIABLES_POR_EJE["x"]


def test_corrector_deriva():
    corrector = analisis.CorrectorDeriva()
    # El cursor queda siempre 0,08 a la izquierda y 0,05 arriba de donde mira.
    azar = random.Random(1)
    for _ in range(8):
        u, v = azar.uniform(0.2, 0.8), azar.uniform(0.2, 0.8)
        predicciones = [corrector.corregir(u - 0.08, v - 0.05) for _ in range(10)]
        assert corrector.observar(predicciones, (u, v), (0.15, 0.08))
    assert corrector.corregir(0.42, 0.45) == pytest.approx((0.5, 0.5), abs=0.005)

    # Lejos del botón (miraba otra cosa) o un objetivo enorme: no se usa.
    antes = (corrector.dx, corrector.dy)
    assert not corrector.observar([(0.1, 0.1)], (0.8, 0.8), (0.1, 0.1))
    assert not corrector.observar([(0.5, 0.5)], (0.55, 0.5), (0.6, 0.4))
    assert (corrector.dx, corrector.dy) == antes

    # Tiene un tope: nunca corre el cursor más de MAXIMO.
    otro = analisis.CorrectorDeriva()
    for _ in range(20):
        otro.observar([otro.corregir(0.3, 0.5)], (0.5, 0.5), (0.1, 0.1))
    assert otro.dx == pytest.approx(analisis.CorrectorDeriva.MAXIMO)


def test_modelo_mirada_desde_dict():
    modelo = analisis.ModeloMirada([0.5, 1.0, 2.0, 0.3], [0.5, 1.0, 2.0, 0.3])
    assert analisis.ModeloMirada.desde_dict(modelo.como_dict()) == modelo
    cruzado = analisis.ModeloMirada([0.5] + [0.1] * 6, [0.4] + [0.2] * 6,
                                    analisis.VARIABLES_CRUZADAS, analisis.VARIABLES_CRUZADAS)
    assert analisis.ModeloMirada.desde_dict(cruzado.como_dict()) == cruzado
    with pytest.raises(ValueError):  # variable desconocida
        analisis.ModeloMirada.desde_dict({"wx": [0.5, 1], "wy": [0.5, 1], "vx": ["os.system"], "vy": ["iris_y"]})
    with pytest.raises(ValueError):  # falta un peso
        analisis.ModeloMirada.desde_dict({"wx": [0.5], "wy": [0.5, 1], "vx": ["iris_x"], "vy": ["iris_y"]})
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
