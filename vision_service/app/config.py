import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _lista(valor):
    return [v.strip() for v in valor.split(",") if v.strip()]


@dataclass
class Config:
    modelo_manos: Path = field(default_factory=lambda: Path(
        os.getenv("VISION_MODELO_MANOS", RAIZ / "modelos" / "hand_landmarker.task")))
    # Opcional: sin este archivo el servicio funciona, pero no ofrece el cursor con la mirada.
    modelo_rostro: Path = field(default_factory=lambda: Path(
        os.getenv("VISION_MODELO_ROSTRO", RAIZ / "modelos" / "face_landmarker.task")))
    modelo_pose: Path = field(default_factory=lambda: Path(
        os.getenv("VISION_MODELO_POSE", RAIZ / "modelos" / "yolov8n-pose.pt")))
    # Misma clave que DJANGO_SECRET_KEY: así se validan los JWT que emite el backend.
    # Vacío = sin autenticación (solo para desarrollo).
    jwt_secreto: str = field(default_factory=lambda: os.getenv("VISION_JWT_SECRETO", ""))
    # Orígenes web permitidos para abrir el WebSocket. Vacío = cualquiera.
    origenes: list = field(default_factory=lambda: _lista(os.getenv("VISION_ORIGENES", "")))
    # YOLO es más pesado que MediaPipe y la postura cambia lento: se corre 1 de cada N frames.
    pose_cada_n_frames: int = field(default_factory=lambda: int(os.getenv("VISION_POSE_CADA_N", "2")))
    tamano_pose: int = field(default_factory=lambda: int(os.getenv("VISION_TAMANO_POSE", "320")))
    tamano_max_frame: int = 400_000  # bytes de un JPEG
    pagina_demo: bool = field(default_factory=lambda: os.getenv("VISION_DEMO", "true").lower() == "true")
