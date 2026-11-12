from django.utils.dateparse import parse_date
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import servicios
from .models import Sesion
from .serializers import (
    FinalizarSerializer,
    IniciarSesionSerializer,
    ResponderSerializer,
    SesionDetalleSerializer,
    SesionSerializer,
)


class SesionViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    viewsets.GenericViewSet):
    """Flujo de una actividad: crear (POST) → responder → finalizar.

    Filtrar el listado con ?paciente=<id> y ?desde=AAAA-MM-DD.
    """

    def get_queryset(self):
        sesiones = Sesion.objects.filter(paciente__cuidador=self.request.user)
        paciente = self.request.query_params.get("paciente")
        if paciente:
            sesiones = sesiones.filter(paciente_id=paciente)
        desde = parse_date(self.request.query_params.get("desde") or "")
        if desde:
            sesiones = sesiones.filter(inicio__date__gte=desde)
        return sesiones.select_related("paciente")

    def get_serializer_class(self):
        return SesionSerializer if self.action == "list" else SesionDetalleSerializer

    def create(self, request, *args, **kwargs):
        entrada = IniciarSesionSerializer(data=request.data, context={"request": request})
        entrada.is_valid(raise_exception=True)
        sesion = servicios.iniciar_sesion(**entrada.validated_data)
        return Response(SesionDetalleSerializer(sesion).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def responder(self, request, pk=None):
        entrada = ResponderSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        resultado = servicios.registrar_respuesta(
            self.get_object(), datos["indice_pregunta"], datos["tiempo_ms"],
            opcion=datos.get("opcion"), orden=datos.get("orden"), errores=datos.get("errores"),
        )
        return Response(resultado)

    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        entrada = FinalizarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        return Response(servicios.finalizar_sesion(self.get_object(), **entrada.validated_data))
