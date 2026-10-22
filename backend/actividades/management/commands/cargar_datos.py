from datetime import date, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from actividades.banco import preguntas_del_banco
from actividades.models import Pregunta
from historia.models import ContenidoHistoria, TipoContenido
from pacientes.models import AdultoMayor, Nivel
from sesiones.models import EstadoSesion, Sesion

# Mismos datos que muestra el prototipo de Figma (pantallas 11 y 15).
SESIONES_DEMO = [
    (6, "memoria", 5),
    (5, "atencion", 6),
    (3, "coordinacion", 7),
    (1, "historia", 6),
    (0, "memoria", 7),
]
HISTORIA_DEMO = [
    ("Boda 1975", "¿Quién está a tu lado en esta foto?", "#038666"),
    ("Su casa", "¿Dónde viviste muchos años?", "#1B4322"),
    ("Nieta Sofía", "Te visita los domingos.", "#E8913A"),
    ("Cumpleaños 70", "Toda la familia vino a celebrar.", "#FBB02D"),
]


def _imagen_demo(texto, color):
    imagen = Image.new("RGB", (800, 600), color)
    dibujo = ImageDraw.Draw(imagen)
    dibujo.text((40, 540), texto, fill="white", font_size=40)
    salida = BytesIO()
    imagen.save(salida, format="PNG")
    return ContentFile(salida.getvalue())


class Command(BaseCommand):
    help = "Carga el banco de preguntas y, con --demo, un cuidador y a Rosa con datos de ejemplo."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Crea datos de demostración.")
        parser.add_argument("--usuario", default="cuidador")
        parser.add_argument("--clave", default="MenteEnMovimiento2026")

    @transaction.atomic
    def handle(self, *args, **opciones):
        creadas = 0
        for datos in preguntas_del_banco():
            claves = {k: datos.pop(k) for k in ("tipo", "nivel", "enunciado", "estimulo_texto")}
            _, nueva = Pregunta.objects.update_or_create(**claves, defaults=datos)
            creadas += nueva
        self.stdout.write(f"Banco de preguntas: {Pregunta.objects.count()} ({creadas} nuevas).")

        if opciones["demo"]:
            self._crear_demo(opciones["usuario"], opciones["clave"])

    def _crear_demo(self, usuario, clave):
        Usuario = get_user_model()
        cuidador, nuevo = Usuario.objects.get_or_create(
            username=usuario, defaults={"first_name": "Cuidador"}
        )
        if nuevo:
            cuidador.set_password(clave)
            cuidador.save()

        rosa, nueva = AdultoMayor.objects.get_or_create(
            cuidador=cuidador,
            nombre="Rosa",
            apellido="Pérez",
            defaults={"fecha_nacimiento": date(1948, 3, 15), "nivel": Nivel.MEDIO},
        )
        if not nueva:
            self.stdout.write("La demo ya existía; no se duplicó.")
            return

        for titulo, pista, color in HISTORIA_DEMO:
            contenido = ContenidoHistoria(paciente=rosa, titulo=titulo, pista=pista,
                                          tipo=TipoContenido.IMAGEN, nombre_original=f"{titulo}.png")
            contenido.archivo.save(f"{titulo}.png", _imagen_demo(titulo, color), save=True)

        ahora = timezone.now()
        for dias_atras, tipo, aciertos in SESIONES_DEMO:
            fin = ahora - timedelta(days=dias_atras, minutes=1)
            sesion = Sesion.objects.create(
                paciente=rosa, tipo=tipo, nivel=Nivel.FACIL, estado=EstadoSesion.FINALIZADA,
                fin=fin, total_preguntas=8, aciertos=aciertos, tiempo_promedio_ms=4200,
                nivel_siguiente=Nivel.MEDIO if aciertos >= 7 else Nivel.FACIL,
            )
            # auto_now_add ignora el valor al crear; se corrige después.
            Sesion.objects.filter(pk=sesion.pk).update(inicio=fin - timedelta(minutes=12))

        self.stdout.write(self.style.SUCCESS(
            f"Demo creada. Usuario: {usuario} · Clave: {clave if nuevo else '(la existente)'}"
        ))
