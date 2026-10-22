"""Carga de los modelos de IA. Se cargan una sola vez al arrancar el servicio."""

import threading

import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision as mp_vision
from ultralytics import YOLO


class Modelos:
    def __init__(self, config):
        self.config = config
        if not config.modelo_manos.exists():
            raise FileNotFoundError(
                f"No se encontró {config.modelo_manos}. Ejecuta: python descargar_modelos.py")
        self._opciones_manos = mp_vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(config.modelo_manos)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._pose = YOLO(str(config.modelo_pose))
        # Una sola instancia de YOLO compartida entre conexiones: se protege con un lock.
        self._candado_pose = threading.Lock()

    def nuevo_detector_manos(self):
        """Cada conexión tiene su propio detector: en modo VIDEO MediaPipe sigue
        la mano entre frames y exige marcas de tiempo crecientes por instancia."""
        return mp_vision.HandLandmarker.create_from_options(self._opciones_manos)

    def detectar_pose(self, imagen_bgr):
        """Devuelve los 17 puntos (x, y, confianza) de la persona más grande, o None."""
        with self._candado_pose:
            resultado = self._pose.predict(imagen_bgr, imgsz=self.config.tamano_pose,
                                           conf=0.5, verbose=False)[0]
        if resultado.boxes is None or len(resultado.boxes) == 0 or resultado.keypoints is None:
            return None
        cajas = resultado.boxes.xywh.cpu().numpy()
        mayor = int((cajas[:, 2] * cajas[:, 3]).argmax())
        return resultado.keypoints.data[mayor].cpu().numpy().tolist()


def imagen_mediapipe(imagen_rgb):
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=imagen_rgb)
