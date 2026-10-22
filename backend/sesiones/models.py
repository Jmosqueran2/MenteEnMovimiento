from django.db import models

from pacientes.models import AdultoMayor, Nivel, TipoActividad


class EstadoSesion(models.TextChoices):
    EN_CURSO = "en_curso", "En curso"
    FINALIZADA = "finalizada", "Finalizada"
    CANCELADA = "cancelada", "Cancelada"


class Ajuste(models.TextChoices):
    SUBIR = "subir", "Subir"
    MANTENER = "mantener", "Mantener"
    BAJAR = "bajar", "Bajar"


class MetodoAjuste(models.TextChoices):
    MODELO = "modelo", "Modelo de IA (scikit-learn)"
    REGLAS = "reglas", "Reglas fijas"


class Sesion(models.Model):
    paciente = models.ForeignKey(AdultoMayor, on_delete=models.CASCADE, related_name="sesiones")
    tipo = models.CharField(max_length=15, choices=TipoActividad.choices)
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    # Preguntas de esta sesión con su orden de opciones ya barajado y la
    # respuesta correcta. Nunca se envía completo al cliente.
    plan = models.JSONField(default=list)
    estado = models.CharField(max_length=12, choices=EstadoSesion.choices,
                              default=EstadoSesion.EN_CURSO)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    # Métricas calculadas al finalizar.
    total_preguntas = models.PositiveSmallIntegerField(default=0)
    aciertos = models.PositiveSmallIntegerField(default=0)
    tiempo_promedio_ms = models.PositiveIntegerField(null=True, blank=True)
    nivel_siguiente = models.CharField(max_length=10, choices=Nivel.choices, blank=True)
    # Decisión de dificultad tomada al finalizar.
    ajuste = models.CharField(max_length=10, choices=Ajuste.choices, blank=True)
    ajuste_metodo = models.CharField(max_length=10, choices=MetodoAjuste.choices, blank=True)
    ajuste_confianza = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "sesión"
        verbose_name_plural = "sesiones"
        ordering = ["-inicio"]

    def __str__(self):
        return f"{self.paciente} · {self.get_tipo_display()} · {self.inicio:%Y-%m-%d %H:%M}"

    @property
    def tasa_aciertos(self):
        if not self.total_preguntas:
            return None
        return round(100 * self.aciertos / self.total_preguntas)

    @property
    def tiempo_promedio_s(self):
        if self.tiempo_promedio_ms is None:
            return None
        return round(self.tiempo_promedio_ms / 1000, 1)

    @property
    def duracion_min(self):
        if not self.fin:
            return None
        return max(1, round((self.fin - self.inicio).total_seconds() / 60))


class Respuesta(models.Model):
    """Cada intento del usuario sobre una pregunta de la sesión."""

    sesion = models.ForeignKey(Sesion, on_delete=models.CASCADE, related_name="respuestas")
    indice_pregunta = models.PositiveSmallIntegerField()
    opcion_elegida = models.PositiveSmallIntegerField()
    correcta = models.BooleanField()
    intento = models.PositiveSmallIntegerField()
    tiempo_ms = models.PositiveIntegerField(help_text="Desde que se mostró la pregunta")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sesion", "indice_pregunta", "intento"]
        constraints = [
            models.UniqueConstraint(fields=["sesion", "indice_pregunta", "intento"],
                                    name="intento_unico"),
        ]
