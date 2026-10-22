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
