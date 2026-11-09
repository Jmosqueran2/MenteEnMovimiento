"""Microservicio de visión de Mente en Movimiento.

Protocolo del WebSocket /ws/vision?token=<access JWT>:
  cliente → servidor
    · binario: un frame JPEG (se recomienda 320×240, calidad 0.7)
    · texto JSON: {"accion": "config", "modo": "seleccion"|"coordinacion", "espejo": true,
                   "puntero": "mano"|"mirada", "modelo_mirada": {"wx": [...], "wy": [...]}}
                  {"accion": "calibrar"}   (con puntero "mirada" también recalibra la mirada)
  servidor → cliente
    · {"tipo": "estado", ...} por cada frame (ver README)
    · {"tipo": "config", ...} al cambiar la configuración
    · {"tipo": "error", "detalle": ...}

El cliente debe enviar el siguiente frame cuando recibe la respuesta del
anterior: así el ritmo se adapta solo a la latencia de la red.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse

from .auth import usuario_del_token
from .config import Config
from .modelos import Modelos
from .procesador import ProcesadorSesion

log = logging.getLogger("vision")
PAGINA_DEMO = Path(__file__).resolve().parent.parent / "static" / "demo.html"


def crear_app(config: Config | None = None) -> FastAPI:
    config = config or Config()

    @asynccontextmanager
    async def ciclo_de_vida(app):
        app.state.modelos = await asyncio.to_thread(Modelos, config)
        if not config.jwt_secreto:
            log.warning("VISION_JWT_SECRETO vacío: el WebSocket no pide autenticación.")
        yield

    app = FastAPI(title="Mente en Movimiento · Visión", lifespan=ciclo_de_vida)

    @app.get("/salud")
    async def salud():
        return {"estado": "ok", "modelos": hasattr(app.state, "modelos"),
                "autenticacion": bool(config.jwt_secreto)}

    if config.pagina_demo:
        @app.get("/", include_in_schema=False)
        async def demo():
            return FileResponse(PAGINA_DEMO)

    @app.websocket("/ws/vision")
    async def vision(websocket: WebSocket, token: str | None = None):
        origen = websocket.headers.get("origin")
        if config.origenes and origen not in config.origenes:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        if config.jwt_secreto and usuario_del_token(token, config.jwt_secreto) is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        procesador = ProcesadorSesion(app.state.modelos)
        try:
            while True:
                mensaje = await websocket.receive()
                if mensaje["type"] == "websocket.disconnect":
                    break
                if mensaje.get("bytes") is not None:
                    datos = mensaje["bytes"]
                    if len(datos) > config.tamano_max_frame:
                        respuesta = {"tipo": "error", "detalle": "Frame demasiado grande."}
                    else:
                        respuesta = await asyncio.to_thread(procesador.procesar, datos)
                else:
                    try:
                        respuesta = procesador.configurar(json.loads(mensaje.get("text") or ""))
                    except (json.JSONDecodeError, AttributeError):
                        respuesta = {"tipo": "error", "detalle": "Mensaje JSON inválido."}
                await websocket.send_json(respuesta)
        except WebSocketDisconnect:
            pass
        finally:
            procesador.cerrar()

    return app


app = crear_app()
