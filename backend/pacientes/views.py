import csv

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from sesiones import servicios
from sesiones.models import EstadoSesion

from .models import AdultoMayor
from .serializers import AdultoMayorSerializer, CuidadorSerializer


def _dias_de(request, defecto=7):
    try:
        dias = int(request.query_params.get("dias", defecto))
    except ValueError:
        dias = defecto
    return min(max(dias, 1), 365)


class YoView(APIView):
    """Datos del cuidador autenticado y de las personas a su cargo."""

    def get(self, request):
        return Response(CuidadorSerializer(request.user).data)


class AdultoMayorViewSet(viewsets.ModelViewSet):
    serializer_class = AdultoMayorSerializer

    def get_queryset(self):
        return AdultoMayor.objects.filter(cuidador=self.request.user)

    def perform_create(self, serializer):
        serializer.save(cuidador=self.request.user)

    @action(detail=True, methods=["get"])
    def resumen(self, request, pk=None):
        """Tarjetas de la pantalla 11 (panel del cuidador)."""
        paciente = self.get_object()
        ultima = (
            paciente.sesiones.filter(estado=EstadoSesion.FINALIZADA).order_by("-fin").first()
        )
        return Response(
            {
                "nivel": paciente.nivel,
                "nivel_texto": paciente.get_nivel_display(),
                "ultima_sesion": None
                if ultima is None
                else {
                    "fecha": ultima.fin,
                    "actividad": ultima.get_tipo_display(),
                    "aciertos": ultima.aciertos,
                    "total": ultima.total_preguntas,
                    "ajuste": ultima.ajuste or None,
                    "ajuste_metodo": ultima.ajuste_metodo or None,
                    "ajuste_confianza": ultima.ajuste_confianza,
                    "nivel_siguiente": ultima.get_nivel_siguiente_display() if ultima.nivel_siguiente else None,
                },
            }
        )

    @action(detail=True, methods=["get"])
    def seguimiento(self, request, pk=None):
        """Indicadores de la pantalla 15. Parámetro opcional ?dias=7."""
        return Response(servicios.calcular_seguimiento(self.get_object(), _dias_de(request)))

    @action(detail=True, methods=["get"], url_path="seguimiento-csv")
    def seguimiento_csv(self, request, pk=None):
        paciente = self.get_object()
        dias = _dias_de(request, defecto=365)
        fecha = timezone.localdate().isoformat()
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = (
            f'attachment; filename="seguimiento_{paciente.nombre.lower()}_{fecha}.csv"'
        )
        respuesta.write("﻿")  # BOM para que Excel respete las tildes
        escritor = csv.writer(respuesta, delimiter=";")
        escritor.writerow(
            [
                "Fecha",
                "Actividad",
                "Nivel",
                "Aciertos",
                "Preguntas",
                "Tasa de aciertos (%)",
                "Tiempo promedio (s)",
                "Duración (min)",
                "Nivel siguiente",
            ]
        )
        for sesion in servicios.sesiones_finalizadas(paciente, dias):
            escritor.writerow(
                [
                    timezone.localtime(sesion.fin).strftime("%Y-%m-%d %H:%M"),
                    sesion.get_tipo_display(),
                    sesion.get_nivel_display(),
                    sesion.aciertos,
                    sesion.total_preguntas,
                    sesion.tasa_aciertos,
                    sesion.tiempo_promedio_s if sesion.tiempo_promedio_s is not None else "",
                    sesion.duracion_min,
                    sesion.get_nivel_siguiente_display() if sesion.nivel_siguiente else "",
                ]
            )
        return respuesta
