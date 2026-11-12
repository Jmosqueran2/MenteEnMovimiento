from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from adaptacion.views import ModeloView
from historia.views import ContenidoHistoriaViewSet
from pacientes.views import AdultoMayorViewSet, RegistroView, YoView
from sesiones.views import SesionViewSet

router = DefaultRouter()
router.register("pacientes", AdultoMayorViewSet, basename="paciente")
router.register("historia", ContenidoHistoriaViewSet, basename="historia")
router.register("sesiones", SesionViewSet, basename="sesion")


def salud(request):
    return JsonResponse({"estado": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/salud/", salud),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/auth/yo/", YoView.as_view(), name="yo"),
    path("api/auth/registro/", RegistroView.as_view(), name="registro"),
    path("api/adaptacion/modelo/", ModeloView.as_view(), name="modelo-dificultad"),
    path("api/", include(router.urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
