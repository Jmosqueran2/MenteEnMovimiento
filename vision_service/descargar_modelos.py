"""Descarga los modelos de IA a la carpeta modelos/ (no se suben a git)."""

import shutil
import urllib.request
from pathlib import Path

MODELOS = Path(__file__).resolve().parent / "modelos"
MANOS_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")


def main():
    MODELOS.mkdir(exist_ok=True)
    manos = MODELOS / "hand_landmarker.task"
    if not manos.exists():
        print("Descargando MediaPipe Hand Landmarker…")
        urllib.request.urlretrieve(MANOS_URL, manos)

    pose = MODELOS / "yolov8n-pose.pt"
    if not pose.exists():
        print("Descargando YOLOv8n-pose…")
        from ultralytics import YOLO
        YOLO("yolov8n-pose.pt")  # ultralytics lo descarga en el directorio actual
        shutil.move("yolov8n-pose.pt", pose)
    print("Modelos listos en", MODELOS)


if __name__ == "__main__":
    main()
