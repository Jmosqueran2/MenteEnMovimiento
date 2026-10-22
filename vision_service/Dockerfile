FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 YOLO_CONFIG_DIR=/tmp/ultralytics
WORKDIR /app

# libgl/glib: dependencias nativas de MediaPipe.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt arreglar_opencv.py descargar_modelos.py ./
RUN pip install --no-cache-dir -r requirements.txt && python arreglar_opencv.py
# Los modelos quedan dentro de la imagen: el contenedor arranca sin internet.
RUN python descargar_modelos.py

COPY app ./app
COPY static ./static

RUN useradd --create-home vision && chown -R vision /app
USER vision
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]
