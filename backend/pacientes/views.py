import csv

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from sesiones import preparacion, servicios
from sesiones.models import EstadoSesion, MotivoAyuda

from . import informe_pdf
from .models import AdultoMayor
from .serializers import AdultoMayorSerializer, CuidadorSerializer, RegistroSerializer

# Lo que se puede cambiar al pulsar «Preparar sesión» en la pantalla 11.
CAMPOS_PREPARAR = ["nivel", "actividades_habilitadas", "tiempo_permanencia_ms", "inicio_autonomo",
                   "mostrar_bloqueadas"]


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


class RegistroView(APIView):
    """GET: si el registro está abierto. POST: crea la cuenta y devuelve los tokens."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "registro"

    def get_throttles(self):
        # Solo cuenta los intentos de crear cuenta, no las consultas.
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get(self, request):
        return Response({"abierto": settings.REGISTRO_ABIERTO})

    def post(self, request):
        if not settings.REGISTRO_ABIERTO:
            return Response(
                {"detail": "La creación de cuentas está desactivada. Pide una cuenta al administrador."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        refresco = RefreshToken.for_user(usuario)
        return Response(
            {"access": str(refresco.access_token), "refresh": str(refresco)},
            status=status.HTTP_201_CREATED,
        )


class AdultoMayorViewSet(viewsets.ModelViewSet):
    serializer_class = AdultoMayorSerializer

    def get_queryset(self):
        return AdultoMayor.objects.filter(cuidador=self.request.user)

    def perform_create(self, serializer):
        serializer.save(cuidador=self.request.user)

    def perform_update(self, serializer):
        preparacion.sincronizar(serializer.save())

    # --- Sesión preparada (pantallas 11 y 03–04) ---------------------------

    @action(detail=True, methods=["get"], url_path="sesion-hoy")
    def sesion_hoy(self, request, pk=None):
        return Response(preparacion.resumen(self.get_object()))

    @action(detail=True, methods=["post"])
    def preparar(self, request, pk=None):
        """«Preparar sesión de [nombre]»: guarda la configuración y deja lista la sesión de hoy."""
        paciente = self.get_object()
        datos = {campo: request.data[campo] for campo in CAMPOS_PREPARAR if campo in request.data}
        # Si no se puede preparar (p. ej. ya está en curso), tampoco se guarda la configuración.
        with transaction.atomic():
            serializer = self.get_serializer(paciente, data=datos, partial=True)
            serializer.is_valid(raise_exception=True)
            paciente = serializer.save()
            prep = preparacion.preparar(paciente)
        return Response(
            {"paciente": self.get_serializer(paciente).data, "sesion_hoy": preparacion.resumen(paciente, prep)},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="sesion-hoy/comenzar")
    def comenzar(self, request, pk=None):
        paciente = self.get_object()
        return Response(preparacion.resumen(paciente, preparacion.comenzar(paciente)))

    @action(detail=True, methods=["post"], url_path="sesion-hoy/terminar")
    def terminar(self, request, pk=None):
        paciente = self.get_object()
        preparacion.terminar(paciente)
        return Response(preparacion.resumen(paciente))

    @action(detail=True, methods=["post"])
    def ayuda(self, request, pk=None):
        """«Pedir ayuda a mi cuidador» (pantallas 05, 09 y 10)."""
        paciente = self.get_object()
        motivo = request.data.get("motivo", MotivoAyuda.OTRO)
        if motivo not in MotivoAyuda.values:
            motivo = MotivoAyuda.OTRO
        preparacion.pedir_ayuda(paciente, motivo)
        return Response(preparacion.resumen(paciente), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="ayuda/atendida")
    def ayuda_atendida(self, request, pk=None):
        paciente = self.get_object()
        preparacion.atender_ayuda(paciente)
        return Response(preparacion.resumen(paciente))

    def perform_destroy(self, paciente):
        # Las sesiones y los contenidos se borran en cascada, pero los archivos
        # de Mi Historia (disco o S3) hay que borrarlos a mano, después de que
        # la base confirme el borrado.
        archivos = [(c.archivo.storage, c.archivo.name) for c in paciente.contenidos.all() if c.archivo]
        with transaction.atomic():
            paciente.delete()
        for almacenamiento, nombre in archivos:
            try:
                almacenamiento.delete(nombre)
            except Exception:  # un archivo que ya no está no debe impedir el borrado
                pass

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

    @action(detail=True, methods=["get"], url_path="seguimiento-pdf")
    def seguimiento_pdf(self, request, pk=None):
        """Informe en PDF de la pantalla 15. Parámetro opcional ?dias=7."""
        paciente = self.get_object()
        dias = _dias_de(request)
        sesiones = list(servicios.sesiones_finalizadas(paciente, dias))
        contenido = informe_pdf.generar(paciente, sesiones, servicios.calcular_seguimiento(paciente, dias), dias)
        fecha = timezone.localdate().isoformat()
        respuesta = HttpResponse(contenido, content_type="application/pdf")
        respuesta["Content-Disposition"] = f'attachment; filename="seguimiento_{paciente.nombre.lower()}_{fecha}.pdf"'
        return respuesta

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
                "Cursor con",
                "Avisos de postura",
                "Minutos con mala postura",
                "Pedidos de ayuda",
                "Error de la mirada (%)",
                "Correcciones de la mirada",
                "Imágenes analizadas por la IA",
            ]
        )
        pedidos = list(paciente.pedidos_ayuda.all())
        for sesion in servicios.sesiones_finalizadas(paciente, dias):
            ia = servicios.resumen_observado(sesion, pedidos)
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
                    informe_pdf.NOMBRE_PUNTERO.get(ia["puntero"], ""),
                    ia["avisos_postura"] if ia["postura_vigilada"] else "",
                    round(ia["segundos_mala_postura"] / 60, 1) if ia["postura_vigilada"] else "",
                    ia["pedidos_ayuda"],
                    round(100 * ia["error_mirada"], 1) if ia["error_mirada"] is not None else "",
                    ia["correcciones_mirada"] if ia["puntero"] == "mirada" else "",
                    ia["imagenes_analizadas"] or "",
                ]
            )
        return respuesta
