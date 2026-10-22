from datetime import date

from django.conf import settings
from django.db import models


class Nivel(models.TextChoices):
    FACIL = "facil", "Fácil"
    MEDIO = "medio", "Medio"
    DIFICIL = "dificil", "Difícil"


class TipoActividad(models.TextChoices):
    MEMORIA = "memoria", "Memoria"
    ATENCION = "atencion", "Atención"
    COORDINACION = "coordinacion", "Coordinación"
    HISTORIA = "historia", "Mi Historia"


class TiempoPermanencia(models.IntegerChoices):
    """Tiempo que la mano debe quedarse quieta sobre una opción para elegirla."""

    NORMAL = 1500, "1,5 segundos"
    PAUSADO = 2000, "2 segundos"
    LENTO = 2500, "2,5 segundos"


def actividades_por_defecto():
    return list(TipoActividad.values)


class AdultoMayor(models.Model):
    cuidador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="adultos_mayores",
    )
    nombre = models.CharField(max_length=80)
    apellido = models.CharField(max_length=80, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    nivel = models.CharField(max_length=10, choices=Nivel.choices, default=Nivel.FACIL)
    tiempo_permanencia_ms = models.PositiveSmallIntegerField(
        choices=TiempoPermanencia.choices,
        default=TiempoPermanencia.NORMAL,
    )
    actividades_habilitadas = models.JSONField(default=actividades_por_defecto)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "adulto mayor"
        verbose_name_plural = "adultos mayores"
        ordering = ["nombre", "apellido"]

    def __str__(self):
        return f"{self.nombre} {self.apellido}".strip()

    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = date.today()
        nacimiento = self.fecha_nacimiento
        return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))

    @property
    def iniciales(self):
        return "".join(parte[0] for parte in (self.nombre, self.apellido) if parte).upper()
