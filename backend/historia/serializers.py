from pathlib import Path

from rest_framework import serializers

from pacientes.models import AdultoMayor

from .models import ContenidoHistoria
from .validadores import validar_archivo


class ContenidoHistoriaSerializer(serializers.ModelSerializer):
    paciente = serializers.PrimaryKeyRelatedField(queryset=AdultoMayor.objects.none())
    url = serializers.SerializerMethodField()

    class Meta:
        model = ContenidoHistoria
        fields = ["id", "paciente", "titulo", "pista", "tipo", "archivo", "nombre_original", "url",
                  "creado"]
        read_only_fields = ["tipo", "nombre_original", "creado"]
        extra_kwargs = {"archivo": {"write_only": True}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            # Un cuidador solo puede subir contenido para las personas a su cargo.
            self.fields["paciente"].queryset = AdultoMayor.objects.filter(cuidador=request.user)

    def get_url(self, contenido):
        return contenido.archivo.url if contenido.archivo else None

    def validate_archivo(self, archivo):
        self._tipo = validar_archivo(archivo)
        return archivo

    def _datos_de_archivo(self, datos):
        if "archivo" in datos:
            datos["tipo"] = self._tipo
            datos["nombre_original"] = Path(datos["archivo"].name).name
        return datos

    def create(self, datos):
        return super().create(self._datos_de_archivo(datos))

    def update(self, contenido, datos):
        anterior = contenido.archivo if "archivo" in datos else None
        contenido = super().update(contenido, self._datos_de_archivo(datos))
        if anterior:
            anterior.storage.delete(anterior.name)
        return contenido
