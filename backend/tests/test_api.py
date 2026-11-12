import shutil
import tempfile
from io import BytesIO, StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.cache import cache
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
        pdf = self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento-pdf/")
        self.assertTrue(pdf.content.startswith(b"%PDF"))  # sin sesiones también se genera
        self.client.force_authenticate(self.otro)
        self.assertEqual(self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento-pdf/").status_code, 404)

    def test_varias_personas_no_se_mezclan(self):
        jorge = self.client.post("/api/pacientes/", {"nombre": "Jorge"}, format="json").data
        self.client.post("/api/historia/", {"paciente": self.rosa.pk, "titulo": "Boda", "archivo": png()},
                         format="multipart")
        self.client.post("/api/sesiones/", {"paciente": jorge["id"], "tipo": "memoria"}, format="json")
        yo = self.client.get("/api/auth/yo/").data
        self.assertEqual({p["nombre"] for p in yo["adultos_mayores"]}, {"Rosa", "Jorge"})
        self.assertEqual(len(self.client.get(f"/api/historia/?paciente={jorge['id']}").data), 0)
        self.assertEqual(len(self.client.get(f"/api/historia/?paciente={self.rosa.pk}").data), 1)
        self.assertEqual(len(self.client.get(f"/api/sesiones/?paciente={self.rosa.pk}").data), 0)
        self.assertEqual(len(self.client.get(f"/api/sesiones/?paciente={jorge['id']}").data), 1)

    def test_eliminar_persona_borra_sus_archivos(self):
        jorge = AdultoMayor.objects.create(cuidador=self.cuidador, nombre="Jorge")
        r = self.client.post("/api/historia/", {"paciente": jorge.pk, "titulo": "Playa", "archivo": png()},
                             format="multipart")
        ruta = Path(MEDIA_TEMPORAL) / jorge.contenidos.get().archivo.name
        self.assertTrue(ruta.exists(), r.data)
        self.client.force_authenticate(self.otro)
        self.assertEqual(self.client.delete(f"/api/pacientes/{jorge.pk}/").status_code, 404)
        self.client.force_authenticate(self.cuidador)
        self.assertEqual(self.client.delete(f"/api/pacientes/{jorge.pk}/").status_code, 204)
        self.assertFalse(AdultoMayor.objects.filter(pk=jorge.pk).exists())
        self.assertFalse(ruta.exists())
        self.assertTrue(AdultoMayor.objects.filter(pk=self.rosa.pk).exists())


class RegistroTest(BaseAPITest):
    def setUp(self):
        cache.clear()  # el límite de registros por IP vive en la caché
        self.client.force_authenticate(None)

    def registrar(self, **cambios):
        datos = {"nombre": "Marta", "usuario": "marta", "email": "", "clave": "Girasoles-del-2026"}
        return self.client.post("/api/auth/registro/", {**datos, **cambios}, format="json")

    def test_crea_cuenta_y_entra(self):
        r = self.registrar()
        self.assertEqual(r.status_code, 201, r.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        yo = self.client.get("/api/auth/yo/").data
        self.assertEqual((yo["username"], yo["first_name"], yo["adultos_mayores"]), ("marta", "Marta", []))
        # La cuenta nueva no ve a las personas de otros cuidadores.
        self.assertEqual(self.client.get(f"/api/pacientes/{self.rosa.pk}/").status_code, 404)

    def test_usuario_repetido(self):
        r = self.registrar(usuario="ANA")
        self.assertEqual(r.status_code, 400)
        self.assertIn("usuario", r.data)

    def test_usuario_con_espacios(self):
        self.assertEqual(self.registrar(usuario="marta lopez").status_code, 400)

    def test_clave_debil(self):
        r = self.registrar(clave="1234")
        self.assertEqual(r.status_code, 400)
        self.assertIn("clave", r.data)

    @override_settings(REGISTRO_ABIERTO=False)
    def test_registro_cerrado(self):
        self.assertEqual(self.client.get("/api/auth/registro/").data, {"abierto": False})
        self.assertEqual(self.registrar().status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username="marta").exists())

    def test_limite_por_ip(self):
        codigos = [self.registrar(usuario=f"u{i}", clave="1234").status_code for i in range(11)]
        self.assertEqual(codigos[-1], 429)


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

        pdf = self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento-pdf/?dias=30")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

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

    def test_lo_que_observo_la_ia(self):
        sesion = Sesion.objects.get(pk=self.iniciar().data["id"])
        for i, item in enumerate(sesion.plan):
            self.responder(sesion, i, respuesta_correcta(item))
        self.client.post(f"/api/pacientes/{self.rosa.pk}/ayuda/", {"motivo": "luz"}, format="json")
        observaciones = {"puntero": "mirada", "postura_vigilada": True, "avisos_encorvado": 2,
                         "avisos_inclinado": 1, "segundos_mala_postura": 95, "error_mirada": 0.047,
                         "correcciones_mirada": 3, "imagenes_analizadas": 4200, "ms_por_imagen": 41.5}
        r = self.client.post(f"/api/sesiones/{sesion.pk}/finalizar/", {"observaciones": observaciones}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

        seguimiento = self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento/").data
        ia = seguimiento["ia"]
        self.assertEqual((ia["avisos_postura"], ia["pedidos_ayuda"], ia["minutos_mala_postura"]), (3, 1, 1.6))
        self.assertEqual(ia["punteros"], {"mirada": 1})
        self.assertEqual(seguimiento["recientes"][0]["ia"]["avisos_postura"], 3)

        csv = self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento-csv/").content.decode("utf-8-sig")
        self.assertIn("Avisos de postura", csv)
        self.assertIn("La mirada", csv)
        pdf = self.client.get(f"/api/pacientes/{self.rosa.pk}/seguimiento-pdf/")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_observaciones_invalidas(self):
        sesion_id = self.iniciar().data["id"]
        for malas in ({"puntero": "teclado"}, {"avisos_encorvado": -1}, {"error_mirada": 3}):
            r = self.client.post(f"/api/sesiones/{sesion_id}/finalizar/", {"observaciones": malas}, format="json")
            self.assertEqual(r.status_code, 400, malas)

    def subir_con_pregunta(self, **extra):
        datos = {"paciente": self.rosa.pk, "titulo": "Boda", "archivo": png("boda.png"),
                 "pregunta": "¿Con quién te casaste?", "opciones": ["Juan", "Pedro", "Luis", "Mario"],
                 "respuesta_correcta": 0, **extra}
        return self.client.post("/api/historia/", datos, format="multipart")

    def test_pregunta_propia(self):
        r = self.subir_con_pregunta()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["opciones"], r.data["respuesta_correcta"]), (["Juan", "Pedro", "Luis", "Mario"], 0))
        # Con una sola foto alcanza, porque tiene su propia pregunta.
        for nivel, opciones in (("facil", 2), ("dificil", 4)):
            self.rosa.nivel = nivel
            self.rosa.save()
            r = self.iniciar("historia")
            self.assertEqual(r.status_code, 201, r.data)
            sesion = Sesion.objects.get(pk=r.data["id"])
            indice, item = next((i, it) for i, it in enumerate(sesion.plan) if it["juego"] == "pregunta_propia")
            publica = r.data["preguntas"][indice]
            self.assertEqual(publica["enunciado"], "¿Con quién te casaste?")
            self.assertEqual(publica["medio"]["tipo"], "imagen")
            self.assertEqual(len(publica["opciones"]), opciones)
            self.assertIn("Juan", [o["texto"] for o in publica["opciones"]])
            self.assertEqual(item["opciones"][item["correcta"]]["texto"], "Juan")
            self.assertTrue(self.responder(sesion, indice, {"opcion": item["correcta"]}).data["correcta"])

    def test_pregunta_propia_validaciones(self):
        casos = [
            ({"opciones": ["Juan"]}, "opciones"),                          # una sola opción
            ({"opciones": ["Juan", "juan "]}, "opciones"),                 # repetidas
            ({"respuesta_correcta": 5}, "respuesta_correcta"),             # fuera de rango
            ({"pregunta": "", "opciones": ["Juan", "Pedro"]}, "pregunta"),  # opciones sin pregunta
        ]
        for extra, campo in casos:
            r = self.subir_con_pregunta(**extra)
            self.assertEqual(r.status_code, 400, extra)
            self.assertIn(campo, r.data)
        # Sin pregunta propia también se puede subir (es opcional).
        r = self.client.post("/api/historia/", {"paciente": self.rosa.pk, "titulo": "Playa", "archivo": png()},
                             format="multipart")
        self.assertEqual((r.status_code, r.data["pregunta"], r.data["opciones"]), (201, "", []))

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


class SesionPreparadaTest(BaseAPITest):
    """Modelo híbrido: el cuidador prepara (11) y el adulto mayor empieza (03–04)."""

    def url(self, accion=""):
        return f"/api/pacientes/{self.rosa.pk}/{accion}"

    def preparar(self, **datos):
        datos.setdefault("actividades_habilitadas", ["memoria", "atencion"])
        return self.client.post(self.url("preparar/"), datos, format="json")

    def terminar_actividad(self, tipo):
        sesion = self.client.post("/api/sesiones/", {"paciente": self.rosa.pk, "tipo": tipo}, format="json")
        self.assertEqual(sesion.status_code, 201, sesion.data)
        plan = Sesion.objects.get(pk=sesion.data["id"]).plan
        for i, item in enumerate(plan):
            self.client.post(f"/api/sesiones/{sesion.data['id']}/responder/",
                             {"indice_pregunta": i, "tiempo_ms": 3000, **respuesta_correcta(item)}, format="json")
        return self.client.post(f"/api/sesiones/{sesion.data['id']}/finalizar/", {}, format="json")

    def test_sin_preparar(self):
        r = self.client.get(self.url("sesion-hoy/"))
        self.assertEqual(r.data["estado"], "no_preparada")
        self.assertFalse(r.data["inicio_autonomo"])  # toda persona nueva empieza acompañada

    def test_preparar_guarda_configuracion_y_queda_lista(self):
        r = self.preparar(nivel="medio", tiempo_permanencia_ms=2000, inicio_autonomo=True)
        self.assertEqual(r.status_code, 201, r.data)
        self.rosa.refresh_from_db()
        self.assertEqual((self.rosa.nivel, self.rosa.tiempo_permanencia_ms, self.rosa.inicio_autonomo),
                         ("medio", 2000, True))
        self.assertEqual(r.data["sesion_hoy"]["estado"], "lista")
        self.assertEqual(r.data["sesion_hoy"]["actividades"], ["memoria", "atencion"])

    def test_mi_historia_sin_fotos_no_se_prepara(self):
        r = self.preparar(actividades_habilitadas=["historia"], nivel="dificil")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Mi Historia", str(r.data))
        self.rosa.refresh_from_db()
        self.assertEqual(self.rosa.nivel, "facil")  # no se guardó nada

    def test_flujo_completo(self):
        self.preparar()
        self.assertEqual(self.client.post(self.url("sesion-hoy/comenzar/")).data["estado"], "en_curso")
        # Solo se puede hacer lo preparado.
        r = self.client.post("/api/sesiones/", {"paciente": self.rosa.pk, "tipo": "coordinacion"}, format="json")
        self.assertEqual(r.status_code, 400)

        self.terminar_actividad("memoria")
        estado = self.client.get(self.url("sesion-hoy/")).data
        self.assertEqual((estado["estado"], estado["hechas"]), ("en_curso", ["memoria"]))

        self.terminar_actividad("atencion")
        estado = self.client.get(self.url("sesion-hoy/")).data
        self.assertEqual(estado["estado"], "terminada")
        self.assertTrue(estado["completa"])
        self.assertEqual(estado["total"], 16)
        self.assertTrue(estado["sugerir_autonomia"])  # acompañada, todo bien y sin pedir ayuda

    def test_no_se_prepara_en_curso(self):
        self.preparar()
        self.client.post(self.url("sesion-hoy/comenzar/"))
        r = self.preparar(nivel="dificil")
        self.assertEqual(r.status_code, 400)
        self.rosa.refresh_from_db()
        self.assertEqual(self.rosa.nivel, "facil")

    def test_dar_por_terminada(self):
        self.preparar()
        self.client.post(self.url("sesion-hoy/comenzar/"))
        r = self.client.post(self.url("sesion-hoy/terminar/"))
        self.assertEqual(r.data["estado"], "terminada")
        self.assertFalse(r.data["completa"])
        self.assertEqual(self.preparar().status_code, 201)  # «Preparar otra»

    def test_comenzar_sin_preparar(self):
        self.assertEqual(self.client.post(self.url("sesion-hoy/comenzar/")).status_code, 400)

    def test_guardar_cambios_actualiza_sesion_lista(self):
        self.preparar()
        self.client.patch(self.url(), {"actividades_habilitadas": ["atencion"]}, format="json")
        self.assertEqual(self.client.get(self.url("sesion-hoy/")).data["actividades"], ["atencion"])

    def test_pedir_ayuda(self):
        self.client.post(self.url("ayuda/"), {"motivo": "camara"}, format="json")
        self.client.post(self.url("ayuda/"), {"motivo": "camara"}, format="json")  # no se duplica
        r = self.client.get(self.url("sesion-hoy/"))
        self.assertEqual(r.data["ayuda"]["motivo_texto"], "Se desconectó la cámara")
        self.assertEqual(self.rosa.pedidos_ayuda.count(), 1)
        self.assertIsNone(self.client.post(self.url("ayuda/atendida/")).data["ayuda"])

    def test_otro_cuidador_no_ve_la_sesion(self):
        self.client.force_authenticate(self.otro)
        self.assertEqual(self.client.get(self.url("sesion-hoy/")).status_code, 404)
        self.assertEqual(self.client.post(self.url("ayuda/")).status_code, 404)
