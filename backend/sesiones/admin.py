from django.contrib import admin

from .models import PedidoAyuda, Respuesta, Sesion, SesionPreparada


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


@admin.register(SesionPreparada)
class SesionPreparadaAdmin(admin.ModelAdmin):
    list_display = ["paciente", "fecha", "estado", "nivel", "preparada", "iniciada", "terminada"]
    list_filter = ["fecha"]


@admin.register(PedidoAyuda)
class PedidoAyudaAdmin(admin.ModelAdmin):
    list_display = ["paciente", "motivo", "creado", "atendido"]
    list_filter = ["atendido", "motivo"]
