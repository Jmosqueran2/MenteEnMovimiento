"""Calibración guiada a la postura: alcance real de la mano en cada dirección."""

from types import SimpleNamespace

import pytest

from app import analisis
from app.procesador import QUIETO_SEGUNDOS, TIEMPO_MAXIMO_PASO, ProcesadorSesion

HOMBROS = {"hombros": {"izquierdo": (0.4, 0.5), "derecho": (0.6, 0.5)}}
# Hasta dónde llega la mano en cada dirección (coordenadas de la imagen).
LIMITES = {"arriba": 0.25, "derecha": 0.75, "abajo": 0.7, "izquierda": 0.3}
REPOSO = (0.5, 0.55)


def procesador():
    modelos = SimpleNamespace(nuevo_detector_manos=lambda: None, mirada_disponible=False)
    return ProcesadorSesion(modelos)


def calibrar_hombros(p):
    for _ in range(20):
        p._actualizar_calibracion(HOMBROS)


def llevar_mano(p, destino, t, quieto=QUIETO_SEGUNDOS + 0.1):
    """Mueve la mano al destino y la deja quieta; devuelve el tiempo final."""
    p._actualizar_alcance(REPOSO, t)
    t += 0.3
    pasos = int(quieto / 0.1) + 1
    for _ in range(pasos):
        p._actualizar_alcance(destino, t)
        t += 0.1
    return t


def destino(direccion):
    x, y = REPOSO
    return (x, LIMITES[direccion]) if direccion in ("arriba", "abajo") else (LIMITES[direccion], y)


def test_zona_desde_alcance():
    seleccion = analisis.zona_desde_alcance(LIMITES, "seleccion")
    coordinacion = analisis.zona_desde_alcance(LIMITES, "coordinacion")
    # En Coordinación se usa el alcance entero; en selección, un poco menos.
    assert (coordinacion.x0, coordinacion.x1, coordinacion.y0, coordinacion.y1) == \
        pytest.approx((0.3, 0.75, 0.25, 0.7))
    assert seleccion.x0 > coordinacion.x0 and seleccion.x1 < coordinacion.x1
    assert seleccion.mapear(0.525, 0.475) == pytest.approx((0.5, 0.5))


def test_zona_desde_alcance_minimo():
    quieto = {"arriba": 0.5, "abajo": 0.5, "izquierda": 0.5, "derecha": 0.5}
    zona = analisis.zona_desde_alcance(quieto, "coordinacion")
    assert zona.x1 - zona.x0 == pytest.approx(analisis.TAMANO_MINIMO_ALCANCE)


def test_alcance_valido():
    assert analisis.alcance_valido(LIMITES)
    assert not analisis.alcance_valido({**LIMITES, "arriba": 2})
    assert not analisis.alcance_valido({"arriba": 0.2})
    assert not analisis.alcance_valido("x")


def test_calibracion_guiada_completa():
    p = procesador()
    p.configurar({"accion": "config", "alcance_guiado": True})
    calibrar_hombros(p)
    assert p.calibracion["estado"] == "alcance"
    assert p.calibracion["direccion"] == "arriba"

    t = 0.0
    p._paso_alcance["inicio"] = t
    for direccion, _ in analisis.DIRECCIONES_ALCANCE:
        assert p.calibracion["direccion"] == direccion
        t = llevar_mano(p, destino(direccion), t)

    assert p.calibracion["estado"] == "completa"
    assert p.calibracion["alcance"] == pytest.approx(LIMITES)
    assert p.zona == analisis.zona_desde_alcance(LIMITES, "seleccion")


def test_la_mano_en_reposo_no_completa_el_paso():
    p = procesador()
    p.configurar({"accion": "config", "alcance_guiado": True})
    calibrar_hombros(p)
    p._paso_alcance["inicio"] = 0.0
    for i in range(30):
        p._actualizar_alcance(REPOSO, i * 0.1)
    assert p.calibracion["estado"] == "alcance"
    assert p.calibracion["paso"] == 0
    assert p.calibracion["quieto"] == 0.0


def test_paso_que_no_se_logra_usa_lo_mas_lejos_o_la_estimacion():
    p = procesador()
    p.configurar({"accion": "config", "alcance_guiado": True})
    calibrar_hombros(p)
    estimada = p.zona
    t = 0.0
    p._paso_alcance["inicio"] = t
    # Arriba: sube un poco, temblando, sin quedarse quieta → se toma lo más alto.
    for i in range(int(TIEMPO_MAXIMO_PASO / 0.1) + 2):
        p._actualizar_alcance((0.5, 0.45 if i % 2 else 0.4), t)
        t += 0.1
    assert p.calibracion["direccion"] == "derecha"
    # Las demás direcciones sin ver la mano → estimación por los hombros.
    for _ in range(3):
        p._actualizar_alcance(None, t)
        t += TIEMPO_MAXIMO_PASO + 0.1
        p._actualizar_alcance(None, t)
    assert p.calibracion["estado"] == "completa"
    assert p.alcance["arriba"] == pytest.approx(0.4)
    assert p.alcance["derecha"] == pytest.approx(estimada.x1)


def test_cambiar_de_modo_conserva_el_alcance():
    p = procesador()
    p.configurar({"accion": "config", "alcance": LIMITES})
    assert p.calibracion["estado"] == "completa"
    p.configurar({"accion": "config", "modo": "coordinacion"})
    assert p.calibracion["estado"] == "completa"
    assert p.zona == analisis.zona_desde_alcance(LIMITES, "coordinacion")
    # «Volver a calibrar» sí descarta el alcance.
    p.configurar({"accion": "calibrar"})
    assert p.calibracion["estado"] == "en_progreso"
    assert p.alcance is None


def test_omitir_alcance():
    p = procesador()
    p.configurar({"accion": "config", "alcance_guiado": True})
    calibrar_hombros(p)
    respuesta = p.configurar({"accion": "omitir_alcance"})
    assert respuesta["calibracion"]["estado"] == "completa"
    assert respuesta["calibracion"]["alcance_omitido"] is True


def test_alcance_invalido():
    assert procesador().configurar({"accion": "config", "alcance": {"arriba": "x"}})["tipo"] == "error"
