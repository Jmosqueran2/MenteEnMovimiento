import shutil
import tempfile
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from adaptacion import caracteristicas, modelo, simulacion
from adaptacion.reglas import aplicar_limites
from pacientes.models import AdultoMayor
from sesiones import servicios
from sesiones.models import Sesion
from tests.test_api import respuesta_correcta, respuesta_incorrecta

CARPETA = tempfile.mkdtemp()
RUTA_MODELO = str(Path(CARPETA) / "dificultad.joblib")


def tearDownModule():
    shutil.rmtree(CARPETA, ignore_errors=True)


class CaracteristicasTest(SimpleTestCase):
    def test_clasifica_preguntas(self):
        R = lambda indice, intento, correcta: SimpleNamespace(  # noqa: E731
            indice_pregunta=indice, intento=intento, correcta=correcta)
        respuestas = [
            R(0, 1, True),                                  # acierto
            R(1, 1, False), R(1, 2, True),                  # reintento
            R(2, 1, False), R(2, 2, False), R(2, 3, False),  # agotada
        ]
        self.assertEqual(caracteristicas.resultados_por_pregunta(respuestas),
                         {"acierto": 1, "reintento": 1, "agotada": 1})

    def test_vector_sin_historial_usa_la_tasa_actual(self):
        v = caracteristicas.vector("medio", 8, {"acierto": 6, "reintento": 1, "agotada": 1}, 4.2, [])
        self.assertEqual(v, [1, 0.75, 0.125, 0.125, 4.2, 0.75, 0])

    def test_simulacion_reproducible(self):
        X1, y1 = simulacion.generar(200, semilla=7)
        X2, y2 = simulacion.generar(200, semilla=7)
        self.assertTrue((X1 == X2).all() and (y1 == y2).all())
        self.assertEqual(X1.shape, (200, len(caracteristicas.NOMBRES)))
        self.assertEqual(set(y1), {-1, 0, 1})

    def test_limites_de_seguridad(self):
        self.assertEqual(aplicar_limites(1, 0.4), 0)    # nunca subir con menos de 60 %
        self.assertEqual(aplicar_limites(-1, 0.9), 0)   # nunca bajar con 85 % o más
        self.assertEqual(aplicar_limites(1, 0.9), 1)


@override_settings(ADAPTACION_MODELO=RUTA_MODELO)
class ModeloTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        clasificador, info = modelo.entrenar(muestras=1500, semilla=1)
        modelo.guardar(clasificador, info, RUTA_MODELO)
        cls.info = info
        cls.cuidador = get_user_model().objects.create_user("ana", password="x")
        cls.rosa = AdultoMayor.objects.create(cuidador=cls.cuidador, nombre="Rosa", nivel="medio")
        call_command("cargar_datos", stdout=StringIO())

    def test_el_modelo_aprende_la_politica(self):
        self.assertGreater(self.info["metricas"]["f1_macro"], 0.8)
        self.assertEqual(set(self.info["importancias"]), set(caracteristicas.NOMBRES))

    def test_decisiones_razonables(self):
        sube, conf_sube = modelo.predecir(caracteristicas.vector(
            "medio", 8, {"acierto": 8, "reintento": 0, "agotada": 0}, 3.0, [0.9, 0.9]))
        baja, _ = modelo.predecir(caracteristicas.vector(
            "medio", 8, {"acierto": 2, "reintento": 2, "agotada": 4}, 9.0, [0.3, 0.25]))
        self.assertEqual(sube, 1)
        self.assertGreater(conf_sube, 0.5)
        self.assertEqual(baja, -1)

    def _jugar(self, correctas):
        sesion = servicios.iniciar_sesion(self.rosa, "memoria")
        for indice, item in enumerate(sesion.plan):
            respuesta = respuesta_correcta(item) if indice < correctas else respuesta_incorrecta(item)
            servicios.registrar_respuesta(sesion, indice, 3000, **respuesta)
        return servicios.finalizar_sesion(Sesion.objects.get(pk=sesion.pk))

    def test_finalizar_usa_el_modelo(self):
        resumen = self._jugar(correctas=8)
        self.assertEqual(resumen["ajuste"]["metodo"], "modelo")
        self.assertEqual(resumen["ajuste"]["ajuste"], "subir")
        self.assertEqual(resumen["nivel_siguiente"], "dificil")
        sesion = self.rosa.sesiones.first()
        self.assertEqual(sesion.ajuste_metodo, "modelo")
        self.assertIsNotNone(sesion.ajuste_confianza)

    def test_api_del_modelo(self):
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(self.cuidador)
        datos = api.get("/api/adaptacion/modelo/").json()
        self.assertTrue(datos["entrenado"])
        self.assertIn("tasa_aciertos", datos["importancias"])


@override_settings(ADAPTACION_MODELO=str(Path(CARPETA) / "no-existe.joblib"))
class SinModeloTest(TestCase):
    def test_respaldo_con_reglas(self):
        cuidador = get_user_model().objects.create_user("luis", password="x")
        rosa = AdultoMayor.objects.create(cuidador=cuidador, nombre="Rosa")
        call_command("cargar_datos", stdout=StringIO())
        sesion = servicios.iniciar_sesion(rosa, "memoria")
        for indice, item in enumerate(sesion.plan):
            servicios.registrar_respuesta(sesion, indice, 2000, **respuesta_correcta(item))
        resumen = servicios.finalizar_sesion(Sesion.objects.get(pk=sesion.pk))
        self.assertEqual(resumen["ajuste"]["metodo"], "reglas")
        self.assertEqual(resumen["nivel_siguiente"], "medio")
