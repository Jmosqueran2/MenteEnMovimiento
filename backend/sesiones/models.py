from django.db import models
from django.utils import timezone

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


class SesionPreparada(models.Model):
    """Lo que el cuidador deja listo para hoy (pantalla 11). El adulto mayor
    la empieza cuando quiere (pantalla 03) y solo ve estas actividades (04).

    Vale para el día en que se preparó; al día siguiente vuelve a "no preparada".
    """

    paciente = models.ForeignKey(AdultoMayor, on_delete=models.CASCADE, related_name="preparadas")
    fecha = models.DateField(default=timezone.localdate)
    actividades = models.JSONField(default=list)
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    preparada = models.DateTimeField(auto_now_add=True)
    iniciada = models.DateTimeField(null=True, blank=True)
    terminada = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "sesión preparada"
        verbose_name_plural = "sesiones preparadas"
        ordering = ["-preparada", "-id"]

    def __str__(self):
        return f"{self.paciente} · {self.fecha} · {self.estado}"

    @property
    def estado(self):
        if self.terminada:
            return "terminada"
        if self.iniciada:
            return "en_curso"
        return "lista"


class MotivoAyuda(models.TextChoices):
    LUZ = "luz", "Hay poca luz"
    CAMARA = "camara", "Se desconectó la cámara"
    CONEXION = "conexion", "Se perdió la conexión"
    ACTIVIDAD = "actividad", "No pudo empezar una actividad"
    OTRO = "otro", "Pidió ayuda"


class PedidoAyuda(models.Model):
    """«Pedir ayuda a mi cuidador» desde las pantallas 05, 09 y 10."""

    paciente = models.ForeignKey(AdultoMayor, on_delete=models.CASCADE, related_name="pedidos_ayuda")
    motivo = models.CharField(max_length=10, choices=MotivoAyuda.choices, default=MotivoAyuda.OTRO)
    creado = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)

    class Meta:
        verbose_name = "pedido de ayuda"
        verbose_name_plural = "pedidos de ayuda"
        ordering = ["-creado", "-id"]


class Sesion(models.Model):
    paciente = models.ForeignKey(AdultoMayor, on_delete=models.CASCADE, related_name="sesiones")
    tipo = models.CharField(max_length=15, choices=TipoActividad.choices)
    preparada = models.ForeignKey(SesionPreparada, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="sesiones")
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
    # Lo que observó la IA de visión durante la actividad (lo junta el
    # navegador y lo manda al finalizar): avisos de postura, de dónde vino el
    # cursor, precisión de la mirada, imágenes analizadas…
    observaciones = models.JSONField(default=dict, blank=True)

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
