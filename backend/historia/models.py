from pathlib import Path
from uuid import uuid4

from django.db import models

from pacientes.models import AdultoMayor


class TipoContenido(models.TextChoices):
    IMAGEN = "imagen", "Imagen"
    AUDIO = "audio", "Audio"


def ruta_contenido(instancia, nombre_archivo):
    extension = Path(nombre_archivo).suffix.lower()
    return f"mi-historia/paciente_{instancia.paciente_id}/{uuid4().hex}{extension}"


class ContenidoHistoria(models.Model):
    """Foto o audio que el cuidador sube para la actividad "Mi Historia"."""

    paciente = models.ForeignKey(AdultoMayor, on_delete=models.CASCADE, related_name="contenidos")
    titulo = models.CharField(max_length=120)
    pista = models.CharField(max_length=200, blank=True)
    tipo = models.CharField(max_length=10, choices=TipoContenido.choices)
    archivo = models.FileField(upload_to=ruta_contenido, max_length=255)
    nombre_original = models.CharField(max_length=255, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "contenido de Mi Historia"
        verbose_name_plural = "contenidos de Mi Historia"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.titulo} ({self.get_tipo_display()})"
