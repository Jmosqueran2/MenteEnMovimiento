"""Procesamiento de los frames de una conexión.

Privacidad: cada frame se decodifica, se analiza en memoria y se descarta.
Nunca se escribe en disco ni se reenvía; al cliente solo vuelven números.
"""

import time
from statistics import median

import cv2
import numpy as np

from . import analisis
from .filtros import FiltroOneEuro
from .modelos import imagen_mediapipe

LADOS = {"Left": "izquierda", "Right": "derecha"}
MUESTRAS_CALIBRACION = 10


class ProcesadorSesion:
    def __init__(self, modelos):
        self.modelos = modelos
        self.detector_manos = modelos.nuevo_detector_manos()
        self.espejo = True
        self.modo = "seleccion"
        self.zona = analisis.ZonaActiva()
        self.filtro_x = FiltroOneEuro()
        self.filtro_y = FiltroOneEuro()
        self.frames = 0
        self.ultimo_ts_ms = 0
        self.postura = None
        self.calibracion = {"estado": "pendiente", "progreso": 0.0}
        self._muestras = []

    def cerrar(self):
        self.detector_manos.close()

    # --- Mensajes de control ---------------------------------------------------

    def configurar(self, mensaje: dict) -> dict:
        accion = mensaje.get("accion")
        if accion == "config":
            if "espejo" in mensaje:
                self.espejo = bool(mensaje["espejo"])
            if mensaje.get("modo") in analisis.ALCANCE:
                self.modo = mensaje["modo"]
                self._iniciar_calibracion()  # la zona depende del modo
        elif accion == "calibrar":
            self._iniciar_calibracion()
        else:
            return {"tipo": "error", "detalle": f"Acción desconocida: {accion!r}"}
        return {"tipo": "config", "espejo": self.espejo, "modo": self.modo,
                "calibracion": self.calibracion}

    def _iniciar_calibracion(self):
        self._muestras = []
        self.calibracion = {"estado": "en_progreso", "progreso": 0.0}

    def _actualizar_calibracion(self, postura):
        if self.calibracion["estado"] == "completa" or not postura or not postura.get("hombros"):
            return
        if self.calibracion["estado"] == "pendiente":
            self._iniciar_calibracion()  # calibración automática la primera vez
        self._muestras.append(postura["hombros"])
        self.calibracion["progreso"] = round(len(self._muestras) / MUESTRAS_CALIBRACION, 2)
        if len(self._muestras) >= MUESTRAS_CALIBRACION:
            def mediana(lado, eje):
                return median(m[lado][eje] for m in self._muestras)
            self.zona = analisis.zona_desde_hombros(
                (mediana("izquierdo", 0), mediana("izquierdo", 1)),
                (mediana("derecho", 0), mediana("derecho", 1)),
                self.modo,
            )
            self.calibracion = {"estado": "completa", "progreso": 1.0,
                                "zona": self.zona.como_dict()}

    # --- Frames ---------------------------------------------------------------

    def procesar(self, jpeg: bytes) -> dict:
        inicio = time.perf_counter()
        imagen = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if imagen is None:
            return {"tipo": "error", "detalle": "El frame no es un JPEG válido."}
        if self.espejo:
            imagen = cv2.flip(imagen, 1)
        alto, ancho = imagen.shape[:2]
        self.frames += 1

        luz = analisis.medir_luz(cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY))
        mano = self._detectar_mano(imagen, ancho, alto)

        if (self.frames - 1) % self.modelos.config.pose_cada_n_frames == 0:
            puntos = self.modelos.detectar_pose(imagen)
            self.postura = analisis.analizar_postura(puntos, ancho, alto) if puntos \
                else {"persona": False}
            self._actualizar_calibracion(self.postura)

        cursor = None
        if mano:
            u, v = self.zona.mapear(*mano.pop("_palma"))
            t = time.monotonic()
            cursor = {"x": round(self.filtro_x(u, t), 4), "y": round(self.filtro_y(v, t), 4)}
        else:
            self.filtro_x.reiniciar()
            self.filtro_y.reiniciar()

        postura_publica = {k: v for k, v in self.postura.items() if k != "hombros"}
        return {
            "tipo": "estado",
            "frame": self.frames,
            "ms": round((time.perf_counter() - inicio) * 1000),
            "cursor": cursor,
            "mano": mano,
            "luz": luz,
            "postura": postura_publica,
            "calibracion": self.calibracion,
            "alertas": analisis.alertas(luz, self.postura),
        }

    def _detectar_mano(self, imagen_bgr, ancho, alto):
        # MediaPipe en modo VIDEO exige marcas de tiempo estrictamente crecientes.
        ts = max(int(time.monotonic() * 1000), self.ultimo_ts_ms + 1)
        self.ultimo_ts_ms = ts
        rgb = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2RGB)
        resultado = self.detector_manos.detect_for_video(imagen_mediapipe(rgb), ts)
        if not resultado.hand_landmarks:
            return None

        puntos = resultado.hand_landmarks[0]
        normalizados = [(p.x, p.y) for p in puntos]
        en_pixeles = [(p.x * ancho, p.y * alto) for p in puntos]
        lado = resultado.handedness[0][0].category_name if resultado.handedness else None
        return {
            "detectada": True,
            "gesto": analisis.clasificar_gesto(en_pixeles),
            "lado": LADOS.get(lado, lado),
            "_palma": analisis.centro_palma(normalizados),
        }
