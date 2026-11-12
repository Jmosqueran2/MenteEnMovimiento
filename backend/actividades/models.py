from django.core.exceptions import ValidationError
from django.db import models

from pacientes.models import Nivel, TipoActividad


class Juego(models.TextChoices):
    """Juegos que se guardan en el banco. Los que se arman al vuelo con este
    mismo contenido (parejas, sigue la figura, alcanza y recuerda y los de Mi
    Historia) están en sesiones/juegos.py."""

    ASOCIACION = "asociacion", "¿Qué objeto va con esto?"
    ELECCION = "eleccion", "Pregunta de opción"
    PAREJA_IGUAL = "pareja_igual", "Encuentra la pareja igual"
    NO_PERTENECE = "no_pertenece", "¿Cuál NO pertenece?"
    OPUESTOS = "opuestos", "Opuestos"
    CLASIFICA = "clasifica", "Clasifica en su grupo"
    SECUENCIA = "secuencia", "Secuencia de la vida diaria"


class Pregunta(models.Model):
    """Pregunta del banco para Memoria, Atención o Coordinación.

    Las preguntas de "Mi Historia" no viven aquí: se arman en cada sesión a
    partir del contenido que subió el cuidador.
    """

    TIPOS = [choice for choice in TipoActividad.choices if choice[0] != TipoActividad.HISTORIA]

    tipo = models.CharField(max_length=15, choices=TIPOS)
    juego = models.CharField(max_length=20, choices=Juego.choices, default=Juego.ELECCION)
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    enunciado = models.CharField(max_length=200)
    estimulo_texto = models.CharField(max_length=80, blank=True)
    estimulo_emoji = models.CharField(max_length=16, blank=True)
    # Lista de {"texto": "Cuchara", "emoji": "🥄"}
    opciones = models.JSONField()
    # En Secuencia, las opciones van en el orden correcto y este campo vale 0.
    respuesta_correcta = models.PositiveSmallIntegerField(help_text="Índice dentro de opciones")
    pista = models.CharField(max_length=200)
    clave = models.CharField(max_length=80, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["tipo", "nivel", "id"]
        constraints = [
            # "clave" (la respuesta correcta) distingue preguntas con el mismo
            # enunciado y sin estímulo, como las de ¿Cuál NO pertenece?
            models.UniqueConstraint(fields=["tipo", "nivel", "juego", "enunciado", "estimulo_texto", "clave"],
                                    name="pregunta_unica"),
        ]

    def __str__(self):
        return f"[{self.get_tipo_display()} · {self.get_nivel_display()}] {self.enunciado}"

    def clean(self):
        maximo = 5 if self.juego == Juego.SECUENCIA else 4
        if not isinstance(self.opciones, list) or not 2 <= len(self.opciones) <= maximo:
            raise ValidationError({"opciones": f"Debe haber entre 2 y {maximo} opciones."})
        if any(not isinstance(op, dict) or not op.get("texto") for op in self.opciones):
            raise ValidationError({"opciones": 'Cada opción necesita al menos {"texto": ...}.'})
        if self.respuesta_correcta >= len(self.opciones):
            raise ValidationError({"respuesta_correcta": "El índice no existe en las opciones."})
