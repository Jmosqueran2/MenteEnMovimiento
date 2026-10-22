from django.contrib import admin

from .models import Pregunta


@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ["enunciado", "estimulo_texto", "tipo", "nivel", "activa"]
    list_filter = ["tipo", "nivel", "activa"]
    search_fields = ["enunciado", "estimulo_texto"]
