import shutil
import tempfile
from io import BytesIO, StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from pacientes.models import AdultoMayor
from sesiones.models import Sesion

MEDIA_TEMPORAL = tempfile.mkdtemp()


def png(nombre="foto.png"):
    salida = BytesIO()
    Image.new("RGB", (10, 10), "green").save(salida, format="PNG")
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type="image/png")


# Sin modelo entrenado: estas pruebas verifican el flujo con las reglas fijas.
@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL, ADAPTACION_MODELO=str(Path(MEDIA_TEMPORAL) / "sin-modelo.joblib"))
class BaseAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_datos", stdout=StringIO())
        Usuario = get_user_model()
        cls.cuidador = Usuario.objects.create_user("ana", password="clave-segura-123")
        cls.otro = Usuario.objects.create_user("luis", password="clave-segura-123")
        cls.rosa = AdultoMayor.objects.create(cuidador=cls.cuidador, nombre="Rosa", apellido="Pérez")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.client.force_authenticate(self.cuidador)


class AutenticacionTest(BaseAPITest):
    def test_requiere_token(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/pacientes/").status_code, 401)

    def test_obtener_token(self):
        self.client.force_authenticate(None)
        r = self.client.post("/api/auth/token/", {"username": "ana", "password": "clave-segura-123"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)


class PacientesTest(BaseAPITest):
    def test_cuidador_solo_ve_a_sus_pacientes(self):
        self.client.force_authenticate(self.otro)
        self.assertEqual(self.client.get("/api/pacientes/").data, [])
        self.assertEqual(self.client.get(f"/api/pacientes/{self.rosa.pk}/").status_code, 404)

    def test_actividad_invalida_rechazada(self):
        r = self.client.patch(f"/api/pacientes/{self.rosa.pk}/",
                              {"actividades_habilitadas": ["memoria", "baile"]}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_seguimiento_sin_datos(self):
        r = self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["sesiones"], 0)
        self.assertIsNone(r.data["tasa_aciertos"])


class HistoriaTest(BaseAPITest):
    def subir(self, archivo, paciente=None):
        return self.client.post("/api/historia/", {
            "paciente": paciente or self.rosa.pk, "titulo": "Boda de Rosa y Juan",
            "pista": "¿Quién está a tu lado?", "archivo": archivo,
        }, format="multipart")

    def test_sube_png(self):
        r = self.subir(png())
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["tipo"], "imagen")
        self.assertTrue(r.data["url"])

    def test_rechaza_pdf(self):
        pdf = SimpleUploadedFile("receta_abuela.pdf", b"%PDF-1.4 ...", "application/pdf")
        r = self.subir(pdf)
        self.assertEqual(r.status_code, 400)
        self.assertIn("receta_abuela.pdf", str(r.data["archivo"][0]))

    def test_rechaza_pdf_renombrado(self):
        r = self.subir(SimpleUploadedFile("foto.jpg", b"%PDF-1.4 ...", "image/jpeg"))
        self.assertEqual(r.status_code, 400)

    def test_no_sube_para_paciente_ajeno(self):
        ajeno = AdultoMayor.objects.create(cuidador=self.otro, nombre="Pedro")
        self.assertEqual(self.subir(png(), paciente=ajeno.pk).status_code, 400)


class SesionTest(BaseAPITest):
    def iniciar(self, tipo="memoria"):
        return self.client.post("/api/sesiones/", {"paciente": self.rosa.pk, "tipo": tipo},
                                format="json")

    def test_flujo_completo_sube_de_nivel(self):
        r = self.iniciar()
        self.assertEqual(r.status_code, 201, r.data)
        preguntas = r.data["preguntas"]
        self.assertEqual(len(preguntas), 8)
        self.assertNotIn("correcta", preguntas[0])
        sesion = Sesion.objects.get(pk=r.data["id"])

        for indice, item in enumerate(sesion.plan):
            if indice == 0:  # Un error en la primera para probar la pista
                incorrecta = (item["correcta"] + 1) % len(item["opciones"])
                fallo = self.client.post(f"/api/sesiones/{sesion.pk}/responder/", {
                    "indice_pregunta": 0, "opcion": incorrecta, "tiempo_ms": 5000}, format="json")
                self.assertFalse(fallo.data["correcta"])
                self.assertTrue(fallo.data["pista"])
                self.assertNotIn("respuesta_correcta", fallo.data)
            ok = self.client.post(f"/api/sesiones/{sesion.pk}/responder/", {
                "indice_pregunta": indice, "opcion": item["correcta"], "tiempo_ms": 3000},
                format="json")
            self.assertTrue(ok.data["correcta"])

        fin = self.client.post(f"/api/sesiones/{sesion.pk}/finalizar/", {}, format="json")
        self.assertEqual(fin.status_code, 200)
        self.assertEqual(fin.data["aciertos"], 7)  # 7 de 8, como en el prototipo
        self.assertEqual(fin.data["nivel_siguiente"], "medio")
        self.rosa.refresh_from_db()
        self.assertEqual(self.rosa.nivel, "medio")

        seguimiento = self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento/").data
        self.assertEqual(seguimiento["sesiones"], 1)
        self.assertEqual(seguimiento["tasa_aciertos"], 88)

        csv = self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento-csv/")
        self.assertEqual(csv.status_code, 200)
        self.assertIn("Memoria", csv.content.decode("utf-8-sig"))

    def test_no_responde_dos_veces_bien(self):
        sesion = Sesion.objects.get(pk=self.iniciar().data["id"])
        datos = {"indice_pregunta": 0, "opcion": sesion.plan[0]["correcta"], "tiempo_ms": 1000}
        self.client.post(f"/api/sesiones/{sesion.pk}/responder/", datos, format="json")
        r = self.client.post(f"/api/sesiones/{sesion.pk}/responder/", datos, format="json")
        self.assertEqual(r.status_code, 400)

    def test_actividad_deshabilitada(self):
        self.rosa.actividades_habilitadas = ["memoria", "atencion", "historia"]
        self.rosa.save()
        self.assertEqual(self.iniciar("coordinacion").status_code, 400)

    def test_mi_historia_necesita_contenido(self):
        self.assertEqual(self.iniciar("historia").status_code, 400)

    def test_mi_historia_con_fotos(self):
        for nombre in ("a.png", "b.png", "c.png"):
            self.client.post("/api/historia/", {"paciente": self.rosa.pk, "titulo": nombre,
                                                "archivo": png(nombre)}, format="multipart")
        r = self.iniciar("historia")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data["preguntas"]), 3)
        self.assertEqual(r.data["preguntas"][0]["medio"]["tipo"], "imagen")

    def test_cancelar_no_cambia_nivel(self):
        sesion_id = self.iniciar().data["id"]
        r = self.client.post(f"/api/sesiones/{sesion_id}/finalizar/", {"cancelada": True},
                             format="json")
        self.assertEqual(r.data["estado"], "cancelada")
        self.assertFalse(r.data["cambio_nivel"])
