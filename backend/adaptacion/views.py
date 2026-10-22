from rest_framework.response import Response
from rest_framework.views import APIView

from .modelo import info_modelo


class ModeloView(APIView):
    """Información del modelo de dificultad: métricas e importancia de variables."""

    def get(self, request):
        info = info_modelo()
        if info is None:
            return Response({"entrenado": False, "metodo": "reglas"})
        return Response({"entrenado": True, "metodo": "modelo", **info})
