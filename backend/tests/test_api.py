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

    def test_perfil_de_movilidad(self):
        self.assertEqual(self.client.get(f"/api/pacientes/{self.rosa.pk}/").data["puntero"], "mano")
        r = self.client.patch(f"/api/pacientes/{self.rosa.pk}/",
                              {"puntero": "mirada", "movilidad": "brazo_derecho", "comandos_voz": True},
                              format="json")
        self.assertEqual(r.status_code, 200)
        self.rosa.refresh_from_db()
        self.assertEqual((self.rosa.puntero, self.rosa.movilidad, self.rosa.comandos_voz),
                         ("mirada", "brazo_derecho", True))
        r = self.client.patch(f"/api/pacientes/{self.rosa.pk}/", {"puntero": "voz"}, format="json")
        self.assertEqual((r.status_code, r.data["puntero"]), (200, "voz"))
        for campo, valor in (("puntero", "pie"), ("movilidad", "volar")):
            r = self.client.patch(f"/api/pacientes/{self.rosa.pk}/", {campo: valor}, format="json")
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


def respuesta_correcta(item):
    """Lo que hay que mandar para acertar, según cómo se responde el juego."""
    modo = item.get("modo", "eleccion")
    if modo == "orden":
        return {"orden": item["correcta"]}
    if modo == "parejas":
        return {"errores": 0}
    return {"opcion": item["correcta"]}


def respuesta_incorrecta(item):
    modo = item.get("modo", "eleccion")
    if modo == "orden":
        return {"orden": list(reversed(item["correcta"]))}
    if modo == "parejas":
        return {"errores": item["ajustes"]["permitido"] + 5}
    return {"opcion": (item["correcta"] + 1) % len(item["opciones"])}


class SesionTest(BaseAPITest):
    def iniciar(self, tipo="memoria"):
        return self.client.post("/api/sesiones/", {"paciente": self.rosa.pk, "tipo": tipo},
                                format="json")

    def responder(self, sesion, indice, respuesta, tiempo_ms=3000):
        return self.client.post(f"/api/sesiones/{sesion.pk}/responder/",
                                {"indice_pregunta": indice, "tiempo_ms": tiempo_ms, **respuesta},
                                format="json")

    def test_flujo_completo_sube_de_nivel(self):
        r = self.iniciar()
        self.assertEqual(r.status_code, 201, r.data)
        preguntas = r.data["preguntas"]
        self.assertEqual(len(preguntas), 8)
        self.assertNotIn("correcta", preguntas[0])
        sesion = Sesion.objects.get(pk=r.data["id"])

        # La primera siempre es de elegir una opción.
        self.assertEqual(sesion.plan[0]["modo"], "eleccion")
        for indice, item in enumerate(sesion.plan):
            if indice == 0:  # Un error en la primera para probar la pista
                fallo = self.responder(sesion, 0, respuesta_incorrecta(item), 5000)
                self.assertFalse(fallo.data["correcta"])
                self.assertTrue(fallo.data["pista"])
                self.assertNotIn("respuesta_correcta", fallo.data)
            ok = self.responder(sesion, indice, respuesta_correcta(item))
            self.assertTrue(ok.data["correcta"], (item["juego"], ok.data))

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

    def test_cada_actividad_mezcla_sus_juegos(self):
        esperados = {
            "memoria": {"asociacion", "opuestos", "clasifica", "secuencia", "parejas"},
            "atencion": {"pareja_igual", "no_pertenece", "eleccion", "sigue_figura"},
            "coordinacion": {"eleccion", "alcanza_recuerda"},
        }
        for nivel in ("facil", "medio", "dificil"):
            self.rosa.nivel = nivel
            self.rosa.save()
            for tipo, juegos in esperados.items():
                r = self.iniciar(tipo)
                self.assertEqual(r.status_code, 201, r.data)
                self.assertEqual(len(r.data["preguntas"]), 8)
                self.assertEqual({p["juego"] for p in r.data["preguntas"]}, juegos, (tipo, nivel))
                self.assertTrue(all("correcta" not in p for p in r.data["preguntas"]))

    def test_dificultad_de_los_juegos(self):
        """Más pasos, más parejas y más cruces al subir de nivel."""
        medidas = {}
        for nivel in ("facil", "dificil"):
            self.rosa.nivel = nivel
            self.rosa.save()
            memoria = Sesion.objects.get(pk=self.iniciar("memoria").data["id"]).plan
            atencion = Sesion.objects.get(pk=self.iniciar("atencion").data["id"]).plan
            secuencia = next(i for i in memoria if i["juego"] == "secuencia")
            parejas = next(i for i in memoria if i["juego"] == "parejas")
            figura = next(i for i in atencion if i["juego"] == "sigue_figura")
            medidas[nivel] = (len(secuencia["opciones"]), len(parejas["opciones"]),
                              figura["ajustes"]["intercambios"])
        self.assertEqual(medidas["facil"], (3, 6, 2))
        self.assertEqual(medidas["dificil"], (5, 12, 6))

    def test_parejas_con_la_mirada(self):
        """Con el cursor de la mirada, Parejas usa menos cartas (más grandes)."""
        self.rosa.nivel, self.rosa.puntero = "dificil", "mirada"
        self.rosa.save()
        plan = Sesion.objects.get(pk=self.iniciar("memoria").data["id"]).plan
        parejas = next(i for i in plan if i["juego"] == "parejas")
        self.assertEqual(len(parejas["opciones"]), 8)
        self.assertEqual(parejas["ajustes"]["permitido"], 6)

    def test_secuencia_y_parejas(self):
        sesion = Sesion.objects.get(pk=self.iniciar("memoria").data["id"])
        indice, secuencia = next((i, item) for i, item in enumerate(sesion.plan) if item["modo"] == "orden")
        fallo = self.responder(sesion, indice, respuesta_incorrecta(secuencia))
        self.assertFalse(fallo.data["correcta"])
        self.assertTrue(fallo.data["puede_reintentar"])
        self.assertEqual(self.responder(sesion, indice, {"orden": [0, 0, 1]}).status_code, 400)
        self.assertTrue(self.responder(sesion, indice, respuesta_correcta(secuencia)).data["correcta"])

        # Parejas con demasiados errores: termina igual, pero como resuelta con ayuda.
        indice, parejas = next((i, item) for i, item in enumerate(sesion.plan) if item["modo"] == "parejas")
        r = self.responder(sesion, indice, respuesta_incorrecta(parejas), 60000)
        self.assertFalse(r.data["correcta"])
        self.assertFalse(r.data["puede_reintentar"])
        self.assertTrue(r.data["completado"])
        guardada = sesion.respuestas.get(indice_pregunta=indice)
        self.assertEqual((guardada.correcta, guardada.intento), (True, 2))
        self.assertLess(guardada.tiempo_ms, 60000)  # tiempo por jugada, no de toda la partida
        self.assertEqual(self.responder(sesion, indice, {"errores": 0}).status_code, 400)

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
        for nombre, anio in (("a.png", 1975), ("b.png", 1990), ("c.png", "")):
            self.client.post("/api/historia/", {"paciente": self.rosa.pk, "titulo": nombre, "anio": anio,
                                                "archivo": png(nombre)}, format="multipart")
        r = self.iniciar("historia")
        self.assertEqual(r.status_code, 201, r.data)
        preguntas = r.data["preguntas"]
        # Cada recuerdo sale como mucho dos veces, más "ordena los recuerdos".
        self.assertEqual(len(preguntas), 7)
        juegos = {p["juego"] for p in preguntas}
        self.assertEqual(juegos, {"momento", "quien_es", "foto_igual", "ordenar_recuerdos"})
        momento = next(p for p in preguntas if p["juego"] == "momento")
        self.assertEqual(momento["medio"]["tipo"], "imagen")
        quien = next(p for p in preguntas if p["juego"] == "quien_es")
        self.assertTrue(all(op["imagen"] for op in quien["opciones"]))
        # Solo se ordenan los que tienen año (a y b): del más antiguo al más reciente.
        sesion = Sesion.objects.get(pk=r.data["id"])
        indice, ordenar = next((i, item) for i, item in enumerate(sesion.plan)
                               if item["juego"] == "ordenar_recuerdos")
        self.assertEqual([ordenar["opciones"][i]["texto"] for i in ordenar["correcta"]], ["a.png", "b.png"])
        self.assertTrue(self.responder(sesion, indice, respuesta_correcta(ordenar)).data["correcta"])

    def test_anio_invalido(self):
        r = self.client.post("/api/historia/", {"paciente": self.rosa.pk, "titulo": "x", "anio": 1800,
                                                "archivo": png()}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_cancelar_no_cambia_nivel(self):
        sesion_id = self.iniciar().data["id"]
        r = self.client.post(f"/api/sesiones/{sesion_id}/finalizar/", {"cancelada": True},
                             format="json")
        self.assertEqual(r.data["estado"], "cancelada")
        self.assertFalse(r.data["cambio_nivel"])
