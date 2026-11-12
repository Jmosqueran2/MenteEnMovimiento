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


class Puntero(models.TextChoices):
    """Qué mueve el cursor en las pantallas de selección."""

    MANO = "mano", "La mano"
    MIRADA = "mirada", "La mirada"
    # Sin cámara: la persona dice en voz alta la opción que quiere.
    VOZ = "voz", "La voz"


class Movilidad(models.TextChoices):
    """Cómo puede moverse la persona; adapta la zona activa y la actividad Coordinación."""

    COMPLETA = "completa", "Ambos brazos"
    REDUCIDA = "reducida", "Movimiento limitado (p. ej. silla de ruedas)"
    BRAZO_IZQUIERDO = "brazo_izquierdo", "Solo el brazo izquierdo"
    BRAZO_DERECHO = "brazo_derecho", "Solo el brazo derecho"
    CABEZA = "cabeza", "Sin usar los brazos (con la cabeza)"


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
    puntero = models.CharField(max_length=10, choices=Puntero.choices, default=Puntero.MANO)
    movilidad = models.CharField(max_length=20, choices=Movilidad.choices, default=Movilidad.COMPLETA)
    # Elegir diciendo la opción en voz alta. Apagado por defecto: según el
    # navegador, el audio puede procesarse en servidores externos.
    comandos_voz = models.BooleanField(default=False)
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
