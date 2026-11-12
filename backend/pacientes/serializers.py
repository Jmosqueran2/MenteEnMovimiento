from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDjango
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
            "inicio_autonomo",
            "rol_cuidador",
            "mostrar_bloqueadas",
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


class RegistroSerializer(serializers.Serializer):
    """Cuenta nueva de cuidador. Cada cuenta ve solo a las personas que crea."""

    nombre = serializers.CharField(max_length=150)
    usuario = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    clave = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_usuario(self, valor):
        Usuario = get_user_model()
        campo = Usuario._meta.get_field(Usuario.USERNAME_FIELD)
        try:
            for validador in campo.validators:
                validador(valor)
        except ErrorDjango:
            raise serializers.ValidationError(
                "El usuario solo puede tener letras, números y los signos @ . + - _ (sin espacios)."
            )
        if Usuario.objects.filter(**{f"{Usuario.USERNAME_FIELD}__iexact": valor}).exists():
            raise serializers.ValidationError("Ese usuario ya existe. Elige otro.")
        return valor

    def validate(self, datos):
        Usuario = get_user_model()
        provisional = Usuario(username=datos["usuario"], first_name=datos["nombre"], email=datos.get("email", ""))
        try:
            validate_password(datos["clave"], user=provisional)
        except ErrorDjango as error:
            raise serializers.ValidationError({"clave": list(error.messages)})
        return datos

    def create(self, datos):
        return get_user_model().objects.create_user(
            username=datos["usuario"],
            email=datos.get("email", ""),
            password=datos["clave"],
            first_name=datos["nombre"],
        )
