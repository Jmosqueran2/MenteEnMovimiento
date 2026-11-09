from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import AdultoMayor, TipoActividad


class AdultoMayorSerializer(serializers.ModelSerializer):
    edad = serializers.ReadOnlyField()
    iniciales = serializers.ReadOnlyField()
    nivel_texto = serializers.CharField(source="get_nivel_display", read_only=True)

    class Meta:
        model = AdultoMayor
        fields = [
            "id",
            "nombre",
            "apellido",
            "fecha_nacimiento",
            "edad",
            "iniciales",
            "nivel",
            "nivel_texto",
            "tiempo_permanencia_ms",
            "actividades_habilitadas",
            "puntero",
            "movilidad",
            "comandos_voz",
            "creado",
            "actualizado",
        ]
        read_only_fields = ["creado", "actualizado"]

    def validate_actividades_habilitadas(self, valor):
        validas = set(TipoActividad.values)
        if not isinstance(valor, list) or any(actividad not in validas for actividad in valor):
            raise serializers.ValidationError(
                f"Las actividades válidas son: {', '.join(TipoActividad.values)}."
            )
        return list(dict.fromkeys(valor))


class CuidadorSerializer(serializers.ModelSerializer):
    adultos_mayores = AdultoMayorSerializer(many=True, read_only=True)

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "first_name", "last_name", "email", "adultos_mayores"]
