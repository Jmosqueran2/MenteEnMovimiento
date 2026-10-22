from django.core.exceptions import ValidationError
from django.db import models

from pacientes.models import Nivel, TipoActividad


class Pregunta(models.Model):
    """Pregunta del banco para Memoria, Atención o Coordinación.

    Las preguntas de "Mi Historia" no viven aquí: se arman en cada sesión a
    partir del contenido que subió el cuidador.
    """

    TIPOS = [choice for choice in TipoActividad.choices if choice[0] != TipoActividad.HISTORIA]

    tipo = models.CharField(max_length=15, choices=TIPOS)
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    enunciado = models.CharField(max_length=200)
    estimulo_texto = models.CharField(max_length=80, blank=True)
    estimulo_emoji = models.CharField(max_length=16, blank=True)
    # Lista de {"texto": "Cuchara", "emoji": "🥄"}
    opciones = models.JSONField()
    respuesta_correcta = models.PositiveSmallIntegerField(help_text="Índice dentro de opciones")
    pista = models.CharField(max_length=200)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["tipo", "nivel", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "nivel", "enunciado", "estimulo_texto"],
                                    name="pregunta_unica"),
        ]

    def __str__(self):
        return f"[{self.get_tipo_display()} · {self.get_nivel_display()}] {self.enunciado}"

    def clean(self):
        if not isinstance(self.opciones, list) or not 2 <= len(self.opciones) <= 4:
            raise ValidationError({"opciones": "Debe haber entre 2 y 4 opciones."})
        if any(not isinstance(op, dict) or not op.get("texto") for op in self.opciones):
            raise ValidationError({"opciones": 'Cada opción necesita al menos {"texto": ...}.'})
        if self.respuesta_correcta >= len(self.opciones):
            raise ValidationError({"respuesta_correcta": "El índice no existe en las opciones."})
