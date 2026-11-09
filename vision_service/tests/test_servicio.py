"""Pruebas de integración con los modelos reales (deben estar en modelos/)."""

import time

import cv2
import jwt
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from ultralytics.utils import ASSETS

from app.config import Config
from app.main import crear_app

SECRETO = "clave-de-prueba-con-al-menos-32-caracteres"


def jpeg(imagen):
    return cv2.imencode(".jpg", imagen)[1].tobytes()


def foto_persona():
    imagen = cv2.imread(str(ASSETS / "zidane.jpg"))
    return jpeg(cv2.resize(imagen, (640, 360)))


@pytest.fixture(scope="module")
def cliente():
    with TestClient(crear_app(Config(jwt_secreto="", pose_cada_n_frames=1))) as c:
        yield c


def test_salud(cliente):
    assert cliente.get("/salud").json()["modelos"] is True


def test_frame_oscuro(cliente):
    with cliente.websocket_connect("/ws/vision") as ws:
        ws.send_bytes(jpeg(np.zeros((240, 320, 3), np.uint8)))
        estado = ws.receive_json()
    assert estado["tipo"] == "estado"
    assert estado["cursor"] is None
    assert "poca_luz" in estado["alertas"]
    assert "sin_persona" in estado["alertas"]


def test_detecta_persona_y_calibra(cliente):
    with cliente.websocket_connect("/ws/vision") as ws:
        for _ in range(10):
            ws.send_bytes(foto_persona())
            estado = ws.receive_json()
    assert estado["postura"]["persona"] is True
    assert estado["postura"]["rostro_visible"] is True
    assert estado["calibracion"]["estado"] == "completa"


def test_mensajes_de_control(cliente):
    with cliente.websocket_connect("/ws/vision") as ws:
        ws.send_text('{"accion": "config", "modo": "coordinacion"}')
        assert ws.receive_json()["modo"] == "coordinacion"
        ws.send_text("no es json")
        assert ws.receive_json()["tipo"] == "error"
        ws.send_bytes(b"no es una imagen")
        assert ws.receive_json()["tipo"] == "error"


def test_exige_token_si_hay_secreto():
    with TestClient(crear_app(Config(jwt_secreto=SECRETO))) as cliente:
        with pytest.raises(WebSocketDisconnect):
            with cliente.websocket_connect("/ws/vision") as ws:
                ws.receive_json()

        token = jwt.encode({"token_type": "access", "user_id": 1, "exp": time.time() + 60},
                           SECRETO, algorithm="HS256")
        with cliente.websocket_connect(f"/ws/vision?token={token}") as ws:
            ws.send_text('{"accion": "calibrar"}')
            assert ws.receive_json()["tipo"] == "config"


def foto_rostro():
    """Zidane, recortado para que la cara ocupe lo que ocuparía frente a la cámara."""
    imagen = cv2.imread(str(ASSETS / "zidane.jpg"))[0:720, 700:1280]
    return jpeg(cv2.resize(imagen, (387, 480)))


def test_puntero_con_la_mirada(cliente):
    with cliente.websocket_connect("/ws/vision") as ws:
        ws.send_text('{"accion": "config", "puntero": "mirada"}')
        config = ws.receive_json()
        assert config["puntero"] == "mirada"
        assert config["mirada_disponible"] is True

        for _ in range(3):
            ws.send_bytes(foto_rostro())
            estado = ws.receive_json()
        assert estado["rostro"]["detectado"] is True
        # La calibración empieza sola al ver la cara; sin calibrar no hay cursor.
        assert estado["calibracion_mirada"]["estado"] == "en_progreso"
        assert estado["calibracion_mirada"]["punto"] == [0.5, 0.5]
        assert estado["cursor"] is None

        # Un modelo guardado por el cliente (p. ej. al reconectar) se restaura.
        ws.send_text('{"accion": "config", "modelo_mirada": {"wx": [0.5, 0, 0], "wy": [0.4, 0, 0]}}')
        assert ws.receive_json()["calibracion_mirada"]["estado"] == "completa"
        ws.send_bytes(foto_rostro())
        estado = ws.receive_json()
        assert estado["cursor"] == {"x": 0.5, "y": 0.4, "fuente": "mirada"}

        # En Coordinación se vuelve a la mano: el ejercicio es estirar los brazos.
        ws.send_text('{"accion": "config", "modo": "coordinacion"}')
        ws.receive_json()
        ws.send_bytes(foto_rostro())
        cursor = ws.receive_json()["cursor"]
        assert cursor is None or cursor["fuente"] == "mano"

        ws.send_text('{"accion": "config", "modelo_mirada": {"wx": [1], "wy": []}}')
        assert ws.receive_json()["tipo"] == "error"


def test_coordinacion_con_la_cabeza(cliente):
    with cliente.websocket_connect("/ws/vision") as ws:
        ws.send_text('{"accion": "config", "movilidad": "cabeza", "modo": "coordinacion"}')
        assert ws.receive_json()["movilidad"] == "cabeza"
        cursores = []
        for _ in range(11):
            ws.send_bytes(foto_rostro())
            cursores.append(ws.receive_json()["cursor"])
    # Primero fija la posición neutra (10 frames) y luego el cursor sale de la cabeza.
    assert all(c is None for c in cursores[:9])
    assert cursores[-1]["fuente"] == "cabeza"
    assert cursores[-1]["x"] == pytest.approx(0.5, abs=0.02)
    assert cursores[-1]["y"] == pytest.approx(0.5, abs=0.02)
