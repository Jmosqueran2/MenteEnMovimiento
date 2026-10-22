from django.contrib import admin

from .models import ContenidoHistoria


@admin.register(ContenidoHistoria)
class ContenidoHistoriaAdmin(admin.ModelAdmin):
    list_display = ["titulo", "paciente", "tipo", "creado"]
    list_filter = ["tipo"]
    search_fields = ["titulo", "paciente__nombre"]
