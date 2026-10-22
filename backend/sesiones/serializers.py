from rest_framework import serializers

from pacientes.models import AdultoMayor, TipoActividad

from . import servicios
from .models import Sesion


class SesionSerializer(serializers.ModelSerializer):
    tipo_texto = serializers.CharField(source="get_tipo_display", read_only=True)
    nivel_texto = serializers.CharField(source="get_nivel_display", read_only=True)

    class Meta:
        model = Sesion
        fields = ["id", "paciente", "tipo", "tipo_texto", "nivel", "nivel_texto", "estado",
                  "inicio", "fin", "total_preguntas", "aciertos", "tiempo_promedio_ms",
                  "nivel_siguiente", "ajuste", "ajuste_metodo", "ajuste_confianza"]
        read_only_fields = fields


class SesionDetalleSerializer(SesionSerializer):
    preguntas = serializers.SerializerMethodField()
    progreso = serializers.SerializerMethodField()
    tiempo_permanencia_ms = serializers.IntegerField(
        source="paciente.tiempo_permanencia_ms", read_only=True
    )

    class Meta(SesionSerializer.Meta):
        fields = SesionSerializer.Meta.fields + ["preguntas", "progreso", "tiempo_permanencia_ms"]
        read_only_fields = fields

    def get_preguntas(self, sesion):
        return servicios.preguntas_publicas(sesion)

    def get_progreso(self, sesion):
        return servicios.progreso(sesion)


class IniciarSesionSerializer(serializers.Serializer):
    paciente = serializers.PrimaryKeyRelatedField(queryset=AdultoMayor.objects.none())
    tipo = serializers.ChoiceField(choices=TipoActividad.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context["request"]
        self.fields["paciente"].queryset = AdultoMayor.objects.filter(cuidador=request.user)


class ResponderSerializer(serializers.Serializer):
    indice_pregunta = serializers.IntegerField(min_value=0)
    opcion = serializers.IntegerField(min_value=0)
    tiempo_ms = serializers.IntegerField(min_value=0, max_value=30 * 60 * 1000)


class FinalizarSerializer(serializers.Serializer):
    cancelada = serializers.BooleanField(default=False)
