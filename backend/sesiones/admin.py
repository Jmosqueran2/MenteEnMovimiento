from django.contrib import admin

from .models import Respuesta, Sesion


class RespuestaInline(admin.TabularInline):
    model = Respuesta
    extra = 0
    readonly_fields = ["indice_pregunta", "opcion_elegida", "correcta", "intento", "tiempo_ms",
                       "creado"]


@admin.register(Sesion)
class SesionAdmin(admin.ModelAdmin):
    list_display = ["paciente", "tipo", "nivel", "estado", "aciertos", "total_preguntas", "inicio"]
    list_filter = ["tipo", "estado", "nivel"]
    readonly_fields = ["plan"]
    inlines = [RespuestaInline]
