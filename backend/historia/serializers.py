from pathlib import Path

from rest_framework import serializers

from pacientes.models import AdultoMayor

from .models import ContenidoHistoria
from .validadores import validar_archivo


MIN_OPCIONES = 2
MAX_OPCIONES = 4


class ContenidoHistoriaSerializer(serializers.ModelSerializer):
    paciente = serializers.PrimaryKeyRelatedField(queryset=AdultoMayor.objects.none())
    url = serializers.SerializerMethodField()
    # En un formulario multipart las opciones llegan como claves repetidas.
    opciones = serializers.ListField(child=serializers.CharField(max_length=80, allow_blank=True),
                                     required=False, max_length=MAX_OPCIONES)

    class Meta:
        model = ContenidoHistoria
        fields = ["id", "paciente", "titulo", "pista", "anio", "pregunta", "opciones", "respuesta_correcta",
                  "tipo", "archivo", "nombre_original", "url", "creado"]
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

    def validate_anio(self, anio):
        if anio is not None and not 1900 <= anio <= 2100:
            raise serializers.ValidationError("Escribe un año entre 1900 y 2100.")
        return anio

    def validate(self, datos):
        """Pregunta propia: o están la pregunta, las opciones y la correcta, o ninguna."""
        actual = self.instance
        pregunta = datos.get("pregunta", actual.pregunta if actual else "").strip()
        opciones = datos.get("opciones", actual.opciones if actual else [])
        opciones = [o.strip() for o in opciones if o and o.strip()]
        correcta = datos.get("respuesta_correcta", actual.respuesta_correcta if actual else None)

        if not pregunta:
            if opciones or correcta is not None:
                raise serializers.ValidationError({"pregunta": "Escribe la pregunta para estas opciones."})
            datos.update(pregunta="", opciones=[], respuesta_correcta=None)
            return datos
        if len(opciones) < MIN_OPCIONES:
            raise serializers.ValidationError({"opciones": f"Escribe al menos {MIN_OPCIONES} opciones."})
        if len({o.casefold() for o in opciones}) != len(opciones):
            raise serializers.ValidationError({"opciones": "Las opciones no pueden repetirse."})
        if correcta is None or not 0 <= correcta < len(opciones):
            raise serializers.ValidationError({"respuesta_correcta": "Marca cuál opción es la correcta."})
        datos.update(pregunta=pregunta, opciones=opciones, respuesta_correcta=correcta)
        return datos

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
