from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .models import ContenidoHistoria
from .serializers import ContenidoHistoriaSerializer


class ContenidoHistoriaViewSet(viewsets.ModelViewSet):
    """Fotos y audios de "Mi Historia". Filtrar con ?paciente=<id>."""

    serializer_class = ContenidoHistoriaSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        contenidos = ContenidoHistoria.objects.filter(paciente__cuidador=self.request.user)
        paciente = self.request.query_params.get("paciente")
        if paciente:
            contenidos = contenidos.filter(paciente_id=paciente)
        return contenidos

    def perform_destroy(self, contenido):
        contenido.archivo.delete(save=False)
        contenido.delete()
