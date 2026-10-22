from django.contrib import admin

from .models import AdultoMayor


@admin.register(AdultoMayor)
class AdultoMayorAdmin(admin.ModelAdmin):
    list_display = ["__str__", "cuidador", "nivel", "tiempo_permanencia_ms", "actualizado"]
    list_filter = ["nivel"]
    search_fields = ["nombre", "apellido", "cuidador__username"]
