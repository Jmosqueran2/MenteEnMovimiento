"""Funciones puras de análisis: no dependen de los modelos, por eso se prueban
con datos sintéticos.

Todas las coordenadas llegan ya en espejo (como se ve en pantalla). Los
puntos geométricos van en píxeles; las posiciones de salida, normalizadas 0–1.
"""

import math
from dataclasses import asdict, dataclass

import numpy as np

# --- Luz ---------------------------------------------------------------------

LUZ_MINIMA = 60        # brillo medio (0–255) por debajo del cual "hay poca luz"
FRACCION_QUEMADA = 0.35  # fracción de píxeles casi blancos que indica contraluz


def medir_luz(gris: np.ndarray) -> dict:
    media = float(gris.mean())
    quemados = float((gris > 245).mean())
    if media < LUZ_MINIMA:
        estado = "baja"
    elif quemados > FRACCION_QUEMADA:
        estado = "contraluz"
    else:
        estado = "ok"
    return {"nivel": round(media), "estado": estado}


# --- Mano (21 puntos de MediaPipe) ---------------------------------------------

MUNECA, PULGAR_PUNTA, PULGAR_IP = 0, 4, 3
DEDOS = {  # nombre: (articulación media PIP, punta)
    "indice": (6, 8),
    "medio": (10, 12),
    "anular": (14, 16),
    "menique": (18, 20),
}
PALMA = (0, 5, 9, 13, 17)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dedos_extendidos(puntos) -> dict:
    muneca = puntos[MUNECA]
    return {
        nombre: _dist(puntos[punta], muneca) > _dist(puntos[pip], muneca) * 1.15
        for nombre, (pip, punta) in DEDOS.items()
    }


def clasificar_gesto(puntos) -> str:
    """abierta | cerrada | apunta | pinza | otra"""
    tamano_palma = _dist(puntos[MUNECA], puntos[9]) or 1.0
    if _dist(puntos[PULGAR_PUNTA], puntos[8]) < 0.35 * tamano_palma:
        return "pinza"
    extendidos = dedos_extendidos(puntos)
    cantidad = sum(extendidos.values())
    if cantidad == 0:
        return "cerrada"
    if cantidad == 1 and extendidos["indice"]:
        return "apunta"
    if cantidad >= 3:
        return "abierta"
    return "otra"


def centro_palma(puntos_normalizados):
    """El centro de la palma no se mueve al cerrar la mano, a diferencia de la
    punta del índice; es más estable para personas con artrosis o temblor."""
    xs = [puntos_normalizados[i][0] for i in PALMA]
    ys = [puntos_normalizados[i][1] for i in PALMA]
    return sum(xs) / len(xs), sum(ys) / len(ys)


# --- Zona activa: qué parte de la imagen equivale a toda la pantalla ---------

@dataclass
class ZonaActiva:
    x0: float = 0.15
    x1: float = 0.85
    y0: float = 0.10
    y1: float = 0.75

    def mapear(self, x, y):
        u = (x - self.x0) / (self.x1 - self.x0)
        v = (y - self.y0) / (self.y1 - self.y0)
        return min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)

    def escalada(self, sensibilidad):
        """Achica la zona alrededor de su centro. Con sensibilidad 2 basta la
        mitad del movimiento para cruzar la pantalla: sirve con cámaras de poco
        ángulo o baja resolución, donde la mano sale de cuadro antes de llegar
        al borde de la zona."""
        if sensibilidad <= 1:
            return self
        cx, cy = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2
        mx = (self.x1 - self.x0) / (2 * sensibilidad)
        my = (self.y1 - self.y0) / (2 * sensibilidad)
        return ZonaActiva(cx - mx, cx + mx, cy - my, cy + my)

    def como_dict(self):
        return {k: round(v, 3) for k, v in asdict(self).items()}


# Sensibilidad del cursor con la mano (la elige el cuidador en cada equipo).
SENSIBILIDAD_MINIMA = 1.0
SENSIBILIDAD_MAXIMA = 3.0


def limitar_sensibilidad(valor) -> float:
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return SENSIBILIDAD_MINIMA
    if valor != valor:  # NaN
        return SENSIBILIDAD_MINIMA
    return min(max(valor, SENSIBILIDAD_MINIMA), SENSIBILIDAD_MAXIMA)


# Cuánto deben estirarse los brazos, en múltiplos del ancho de hombros.
ALCANCE = {"seleccion": 1.1, "coordinacion": 1.6}
TAMANO_MINIMO_ZONA = 0.25

# Movilidad de la persona (la elige el cuidador en su perfil).
MOVILIDADES = ("completa", "reducida", "brazo_izquierdo", "brazo_derecho", "cabeza")
# Movimiento limitado (silla de ruedas, hombros rígidos): menos alcance y casi
# nada por encima de la cabeza, donde más cuesta llegar sentado.
FACTOR_REDUCIDA = 0.8
ARRIBA_REDUCIDA = 0.6
# Con un solo brazo la zona se corre hacia ese lado: cruzar el cuerpo cansa.
CORRIMIENTO_UN_BRAZO = 0.6


def zona_desde_hombros(hombro_izq, hombro_der, modo="seleccion", movilidad="completa") -> ZonaActiva:
    """Calibración: adapta la zona activa al cuerpo y a la distancia de la persona.

    Los hombros llegan normalizados (0–1) y la imagen está en espejo, así que el
    brazo izquierdo de la persona queda a la izquierda de la pantalla: con un
    solo brazo la zona se corre hacia ese lado de la imagen (no se usan las
    etiquetas izquierda/derecha de YOLO, que el espejo invierte).
    En modo coordinación la zona es más grande, así que para llegar a las
    esquinas hay que estirar los brazos.
    """
    alcance = ALCANCE.get(modo, ALCANCE["seleccion"])
    arriba = 1.1
    if movilidad == "reducida":
        alcance *= FACTOR_REDUCIDA
        arriba = ARRIBA_REDUCIDA
    cx = (hombro_izq[0] + hombro_der[0]) / 2
    cy = (hombro_izq[1] + hombro_der[1]) / 2
    ancho = max(abs(hombro_izq[0] - hombro_der[0]), 0.05)
    if movilidad in ("brazo_izquierdo", "brazo_derecho"):
        lado = -1 if movilidad == "brazo_izquierdo" else 1
        cx += lado * ancho * CORRIMIENTO_UN_BRAZO

    medio_ancho = max(ancho * alcance, TAMANO_MINIMO_ZONA / 2)
    x0, x1 = cx - medio_ancho, cx + medio_ancho
    y0 = cy - ancho * alcance * arriba  # hacia arriba: por encima de la cabeza
    y1 = cy + ancho * alcance * 0.5     # hacia abajo: a la altura del pecho
    if y1 - y0 < TAMANO_MINIMO_ZONA:
        y1 = y0 + TAMANO_MINIMO_ZONA
    return ZonaActiva(max(x0, 0.0), min(x1, 1.0), max(y0, 0.0), min(y1, 1.0))


# --- Calibración guiada a la postura: alcance real de la mano -----------------
# La persona lleva la mano hacia cada lado hasta donde llega cómoda y se queda
# quieta. Así la zona se ajusta a su cuerpo real (silla de ruedas, un brazo,
# hombros rígidos), no a una estimación a partir de los hombros.

# Orden de los pasos y dónde se dibuja la flecha en la pantalla (x, y).
DIRECCIONES_ALCANCE = (
    ("arriba", (0.5, 0.1)),
    ("derecha", (0.9, 0.5)),
    ("abajo", (0.5, 0.9)),
    ("izquierda", (0.1, 0.5)),
)
# Con alcance real, la selección usa la zona un poco más chica: así los
# botones de los bordes se alcanzan sin estirarse del todo. En Coordinación se
# usa entera: el ejercicio es llegar a su límite cómodo.
MARGEN_SELECCION_ALCANCE = 0.1
# Aunque casi no se mueva, la zona no puede ser un punto (el cursor saltaría).
TAMANO_MINIMO_ALCANCE = 0.12


def alcance_valido(alcance) -> bool:
    try:
        return all(0.0 <= float(alcance[d]) <= 1.0 for d, _ in DIRECCIONES_ALCANCE)
    except (KeyError, TypeError, ValueError):
        return False


def zona_desde_alcance(alcance, modo="seleccion") -> ZonaActiva:
    """Zona activa a partir de hasta dónde llegó la mano en cada dirección
    (coordenadas normalizadas de la imagen en espejo)."""

    def eje(a, b):
        a, b = sorted((float(a), float(b)))
        if b - a < TAMANO_MINIMO_ALCANCE:
            centro = (a + b) / 2
            a, b = centro - TAMANO_MINIMO_ALCANCE / 2, centro + TAMANO_MINIMO_ALCANCE / 2
        if modo != "coordinacion":
            margen = (b - a) * MARGEN_SELECCION_ALCANCE
            a, b = a + margen, b - margen
        return max(a, 0.0), min(b, 1.0)

    x0, x1 = eje(alcance["izquierda"], alcance["derecha"])
    y0, y1 = eje(alcance["arriba"], alcance["abajo"])
    return ZonaActiva(x0, x1, y0, y1)


# --- Postura (17 puntos COCO de YOLOv8-Pose) -----------------------------------

NARIZ, OJO_IZQ, OJO_DER = 0, 1, 2
HOMBRO_IZQ, HOMBRO_DER, CODO_IZQ, CODO_DER, MUNECA_IZQ, MUNECA_DER = 5, 6, 7, 8, 9, 10
CONFIANZA_MINIMA = 0.5
ANGULO_BRAZO_EXTENDIDO = 150  # grados en el codo


def angulo(a, b, c):
    """Ángulo en b (grados) formado por los segmentos b→a y b→c."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    norma = math.hypot(*v1) * math.hypot(*v2)
    if norma == 0:
        return 0.0
    coseno = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / norma))
    return math.degrees(math.acos(coseno))


def analizar_postura(puntos, ancho_img, alto_img) -> dict:
    """puntos: 17 × (x_px, y_px, confianza) de una persona."""
    def visible(i):
        return puntos[i][2] >= CONFIANZA_MINIMA

    def norm(i):
        return puntos[i][0] / ancho_img, puntos[i][1] / alto_img

    resultado = {
        "persona": True,
        "rostro_visible": visible(NARIZ) and (visible(OJO_IZQ) or visible(OJO_DER)),
        "hombros_visibles": visible(HOMBRO_IZQ) and visible(HOMBRO_DER),
        "distancia": None,
        "centrado": None,
        "hombros_nivelados": None,
        "brazos": {},
        "hombros": None,
    }

    if resultado["hombros_visibles"]:
        hi, hd = norm(HOMBRO_IZQ), norm(HOMBRO_DER)
        ancho = abs(hi[0] - hd[0])
        cx = (hi[0] + hd[0]) / 2
        resultado["distancia"] = "lejos" if ancho < 0.12 else "cerca" if ancho > 0.5 else "ok"
        resultado["centrado"] = 0.3 <= cx <= 0.7
        inclinacion = abs(puntos[HOMBRO_IZQ][1] - puntos[HOMBRO_DER][1]) / max(
            abs(puntos[HOMBRO_IZQ][0] - puntos[HOMBRO_DER][0]), 1.0)
        resultado["hombros_nivelados"] = inclinacion < 0.25
        resultado["hombros"] = {"izquierdo": hi, "derecho": hd}
        resultado["medidas"] = medidas_postura(puntos)

    for lado, (h, c, m) in {"izquierdo": (HOMBRO_IZQ, CODO_IZQ, MUNECA_IZQ),
                            "derecho": (HOMBRO_DER, CODO_DER, MUNECA_DER)}.items():
        if visible(h) and visible(c) and visible(m):
            grados = angulo(puntos[h][:2], puntos[c][:2], puntos[m][:2])
            resultado["brazos"][lado] = {
                "angulo_codo": round(grados),
                "extendido": grados >= ANGULO_BRAZO_EXTENDIDO,
                "levantado": puntos[m][1] < puntos[h][1],
            }
    if resultado.get("medidas"):
        # Mano por encima del codo: está apuntando (cursor con la mano) y eso
        # inclina los hombros sin que esté mal sentada.
        resultado["medidas"]["brazo_activo"] = any(
            visible(c) and visible(m) and puntos[m][1] < puntos[c][1]
            for c, m in ((CODO_IZQ, MUNECA_IZQ), (CODO_DER, MUNECA_DER)))
    return resultado


# --- Postura al estar sentado ---------------------------------------------------
#
# Con una cámara frontal no se ve la espalda, pero encorvarse se nota en la
# cabeza: baja y se adelanta, y la nariz queda más cerca de la línea de los
# hombros. Cada cámara está a otra altura y cada persona es distinta, así que
# se compara con su propia postura al empezar las actividades, no con un valor fijo.

def medidas_postura(puntos) -> dict:
    """puntos: 17 × (x_px, y_px, confianza). Requiere los dos hombros visibles."""
    hi, hd = puntos[HOMBRO_IZQ], puntos[HOMBRO_DER]
    ancho = math.hypot(hd[0] - hi[0], hd[1] - hi[1]) or 1.0
    # Ángulo de la línea de hombros respecto de la horizontal (0 = nivelados).
    grados = math.degrees(math.atan2(hd[1] - hi[1], hd[0] - hi[0]))
    if grados > 90:
        grados -= 180
    elif grados < -90:
        grados += 180
    medio_y = (hi[1] + hd[1]) / 2
    altura = (medio_y - puntos[NARIZ][1]) / ancho if puntos[NARIZ][2] >= CONFIANZA_MINIMA else None
    return {"altura_cabeza": altura, "inclinacion_hombros": grados, "ancho_hombros": ancho}


class MonitorPostura:
    """Avisa si la persona se encorva o se ladea durante las actividades.

    1. Mide su postura de referencia con las primeras muestras (al empezar,
       cuando acaba de sentarse para las actividades).
    2. Si la cabeza baja mucho respecto de los hombros, o los hombros se
       inclinan, durante unos segundos seguidos, avisa.
    3. El aviso se quita cuando vuelve a una postura cercana a la de
       referencia (con un margen, para que no parpadee).
    """

    MUESTRAS_REFERENCIA = 12
    BAJA_CABEZA = 0.75         # encorvado: la cabeza queda a menos del 75 % de su altura habitual
    RECUPERA_CABEZA = 0.85     # se quita el aviso al volver por encima del 85 %
    # Si ya empieza encorvada, su "altura habitual" sería la de encorvada y
    # nunca se avisaría. Por eso la referencia nunca es menor que esto: sentada
    # derecha frente a una cámara web la nariz queda a ~0,5–0,65 anchos de
    # hombros sobre ellos; encorvada, cerca de 0,3.
    ALTURA_REFERENCIA_MINIMA = 0.45
    INCLINA_HOMBROS = 12.0     # grados más que en la referencia
    RECUPERA_HOMBROS = 7.0
    # Los hombros de referencia tampoco pueden empezar torcidos: como mucho esto.
    INCLINACION_REFERENCIA_MAXIMA = 5.0
    SEGUNDOS_AVISO = 3.0       # la mala postura tiene que durar esto (mirar abajo un momento no cuenta)
    SEGUNDOS_RECUPERA = 1.0

    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self._referencia = []
        self.altura_ref = None
        self.inclinacion_ref = None
        self.aviso = None
        self._desde_mala = None
        self._desde_buena = None

    def pausar(self):
        """Durante Coordinación (estirar los brazos inclina los hombros a propósito)."""
        self.aviso = None
        self._desde_mala = None
        self._desde_buena = None

    @property
    def estado(self):
        if self.altura_ref is None:
            return "midiendo"
        return self.aviso or "buena"

    def _clasificar(self, medidas, recuperando):
        limite_cabeza = self.RECUPERA_CABEZA if recuperando else self.BAJA_CABEZA
        limite_hombros = self.RECUPERA_HOMBROS if recuperando else self.INCLINA_HOMBROS
        altura = medidas.get("altura_cabeza")
        if altura is not None and altura < self.altura_ref * limite_cabeza:
            return "encorvado"
        if medidas.get("brazo_activo"):
            return None  # apuntando con la mano: los hombros no dicen nada
        if abs(medidas["inclinacion_hombros"] - self.inclinacion_ref) > limite_hombros:
            return "inclinado"
        return None

    def actualizar(self, medidas, t) -> str:
        """medidas: de medidas_postura (o None si no se ven los hombros); t en segundos."""
        if not medidas:
            return self.estado  # sin datos no se cambia nada
        if self.altura_ref is None:
            if medidas.get("altura_cabeza") is not None and medidas["altura_cabeza"] > 0:
                self._referencia.append(medidas)
            if len(self._referencia) >= self.MUESTRAS_REFERENCIA:
                medida = float(np.median([m["altura_cabeza"] for m in self._referencia]))
                self.altura_ref = max(medida, self.ALTURA_REFERENCIA_MINIMA)
                quietas = [m["inclinacion_hombros"] for m in self._referencia if not m.get("brazo_activo")]
                inclinacion = float(np.median(quietas)) if quietas else 0.0
                tope = self.INCLINACION_REFERENCIA_MAXIMA
                self.inclinacion_ref = min(max(inclinacion, -tope), tope)
            return self.estado

        problema = self._clasificar(medidas, recuperando=self.aviso is not None)
        if self.aviso is None:
            if problema:
                self._desde_mala = self._desde_mala if self._desde_mala is not None else t
                if t - self._desde_mala >= self.SEGUNDOS_AVISO:
                    self.aviso = problema
                    self._desde_buena = None
            else:
                self._desde_mala = None
        elif problema:
            self._desde_buena = None
            self.aviso = problema  # p. ej. pasó de ladearse a encorvarse
        else:
            self._desde_buena = self._desde_buena if self._desde_buena is not None else t
            if t - self._desde_buena >= self.SEGUNDOS_RECUPERA:
                self.aviso = None
                self._desde_mala = None
        return self.estado


def alertas(luz, postura) -> list:
    """Problemas que la interfaz debe mostrarle al usuario (pantallas de error)."""
    lista = []
    if luz["estado"] == "baja":
        lista.append("poca_luz")
    elif luz["estado"] == "contraluz":
        lista.append("contraluz")
    if postura is None:
        return lista
    if not postura["persona"]:
        lista.append("sin_persona")
        return lista
    if not postura["rostro_visible"]:
        lista.append("rostro_no_visible")
    if postura["distancia"] == "lejos":
        lista.append("muy_lejos")
    elif postura["distancia"] == "cerca":
        lista.append("muy_cerca")
    if postura["centrado"] is False:
        lista.append("descentrado")
    return lista


# --- Mirada (478 puntos de MediaPipe Face Landmarker, con iris) ----------------
#
# Con una cámara web común el iris mide pocos píxeles, así que solo con los ojos
# el cursor temblaría mucho. Se combinan dos señales: hacia dónde apunta la
# cabeza (gruesa pero estable) y hacia dónde se mueven los ojos dentro de ella
# (fina). La calibración aprende cuánto pesa cada una en esta persona.

OJOS = (  # (esquina, esquina, párpado superior, párpado inferior, iris: centro + 4 del borde)
    (33, 133, 159, 145, (468, 469, 470, 471, 472)),
    (362, 263, 386, 374, (473, 474, 475, 476, 477)),
)
PUNTA_NARIZ = 1
# Alto / ancho del ojo por debajo del cual se considera parpadeo, mientras aún no
# se conoce la apertura habitual de la persona.
OJO_CERRADO = 0.08
# Con la apertura habitual ya medida: parpadeo = menos de esta fracción de ella.
# Así no se confunde con un parpadeo eterno a quien tiene los párpados caídos.
FRACCION_PARPADEO = 0.55

# Dónde aparece el punto que la persona debe mirar al calibrar (0–1 de la pantalla).
# 9 puntos (centro, esquinas y lados): con 5 el ajuste vertical quedaba muy pobre.
PUNTOS_CALIBRACION_MIRADA = (
    (0.5, 0.5),
    (0.12, 0.15), (0.5, 0.15), (0.88, 0.15),
    (0.88, 0.5), (0.88, 0.85), (0.5, 0.85),
    (0.12, 0.85), (0.12, 0.5),
)
# Regularización (ridge) que se prueba en cada calibración, sobre variables
# estandarizadas. Se elige la que mejor predice puntos que no se usaron.
REGULARIZACIONES = (1e-4, 1e-3, 1e-2, 1e-1)

# Modelos candidatos, de más simple a más completo. La calibración elige uno
# por validación cruzada dejando un punto afuera: así solo se usa un modelo más
# complejo si de verdad predice mejor los lugares que la persona no miró.
#  - por_eje: la X de pantalla sale solo de rasgos X (el modelo original).
#  - cruzado: cada eje usa los rasgos de ambos. La cámara está encima de la
#    pantalla, así que mirar hacia un lado también mueve el iris en vertical.
#  - curvo: además, términos cuadráticos del iris, que se "satura" hacia los
#    bordes del ojo.
VARIABLES_POR_EJE = {"x": ("cabeza_x", "iris_x", "mirada_x"), "y": ("cabeza_y", "iris_y", "mirada_y")}
VARIABLES_CRUZADAS = ("cabeza_x", "cabeza_y", "iris_x", "iris_y", "mirada_x", "mirada_y")
VARIABLES_CURVAS = VARIABLES_CRUZADAS + ("iris_x*iris_x", "iris_x*iris_y", "iris_y*iris_y")
CANDIDATOS_MIRADA = (
    ("por_eje", VARIABLES_POR_EJE["x"], VARIABLES_POR_EJE["y"]),
    ("cruzado", VARIABLES_CRUZADAS, VARIABLES_CRUZADAS),
    ("curvo", VARIABLES_CURVAS, VARIABLES_CURVAS),
)
# Un modelo más complejo tiene que mejorar al más simple al menos en esta proporción.
MEJORA_MINIMA = 0.95
VARIABLES_VALIDAS = set(VARIABLES_CURVAS)
# Muestras de un mismo punto más alejadas que esto (en MAD) de su mediana se
# descartan antes de ajustar: la persona movió los ojos mientras tanto.
LIMITE_MAD = 3.5
RASGOS_ROBUSTOS = ("cabeza_x", "cabeza_y", "iris_x", "iris_y")


def _media(puntos, indices):
    return (sum(puntos[i][0] for i in indices) / len(indices),
            sum(puntos[i][1] for i in indices) / len(indices))


def _girar(dx, dy, angulo):
    """Gira el vector (dx, dy) en -angulo: lo lleva a los ejes de la cara."""
    c, s = math.cos(angulo), math.sin(angulo)
    return c * dx + s * dy, -s * dx + c * dy


def mirada_blendshapes(blendshapes) -> tuple:
    """Dirección de la mirada según MediaPipe (dict nombre → 0–1), o (0, 0).

    x > 0 cuando ambos ojos miran hacia el mismo lado; el signo exacto lo
    aprende la calibración, así que da igual que la imagen vaya en espejo.
    """
    if not blendshapes:
        return 0.0, 0.0
    b = blendshapes.get
    x = ((b("eyeLookOutLeft", 0) - b("eyeLookInLeft", 0))
         - (b("eyeLookOutRight", 0) - b("eyeLookInRight", 0))) / 2
    y = ((b("eyeLookUpLeft", 0) + b("eyeLookUpRight", 0))
         - (b("eyeLookDownLeft", 0) + b("eyeLookDownRight", 0))) / 2
    return x, y


def rasgos_mirada(puntos, blendshapes=None, apertura_habitual=None) -> dict:
    """puntos: 478 × (x_px, y_px). Las medidas se dividen por el tamaño de la
    cara, así no cambian si la persona se acerca, se aleja o se corre de lado.

    El iris se mide respecto de las esquinas del ojo y no de los párpados: el
    párpado superior acompaña a la mirada al subir y bajar, y anulaba la señal.

    Todo se mide en los ejes de la cara, no de la imagen: si la persona ladea
    la cabeza, mirar a un lado no se confunde con mirar hacia arriba.
    """
    centros, iris_x, iris_y, aperturas = [], [], [], []
    for a, b, sup, inf, iris in OJOS:
        ancho = _dist(puntos[a], puntos[b]) or 1.0
        cx = (puntos[a][0] + puntos[b][0]) / 2
        cy = (puntos[a][1] + puntos[b][1]) / 2
        centros.append((cx, cy))
        # Ángulo de la línea entre las esquinas de este ojo (0 con la cabeza derecha).
        angulo = math.atan2(puntos[b][1] - puntos[a][1], puntos[b][0] - puntos[a][0])
        ix, iy = _media(puntos, iris)  # 5 puntos: tiembla menos que solo el centro
        rx, ry = _girar(ix - cx, iy - cy, angulo)
        iris_x.append(rx / ancho)
        iris_y.append(ry / ancho)
        aperturas.append(_dist(puntos[sup], puntos[inf]) / ancho)

    entre_ojos = _dist(*centros) or 1.0
    medio = ((centros[0][0] + centros[1][0]) / 2, (centros[0][1] + centros[1][1]) / 2)
    inclinacion = math.atan2(centros[1][1] - centros[0][1], centros[1][0] - centros[0][0])
    nariz = puntos[PUNTA_NARIZ]
    cabeza_x, cabeza_y = _girar(nariz[0] - medio[0], nariz[1] - medio[1], inclinacion)
    apertura = sum(aperturas) / 2
    umbral = apertura_habitual * FRACCION_PARPADEO if apertura_habitual else OJO_CERRADO
    mirada_x, mirada_y = mirada_blendshapes(blendshapes)
    return {
        "cabeza_x": cabeza_x / entre_ojos,
        "cabeza_y": cabeza_y / entre_ojos,
        "iris_x": sum(iris_x) / 2,
        "iris_y": sum(iris_y) / 2,
        "mirada_x": mirada_x,
        "mirada_y": mirada_y,
        "inclinacion": inclinacion,
        "apertura": apertura,
        "ojos_abiertos": apertura >= umbral,
    }


def _valor(rasgos, nombre):
    if "*" in nombre:
        a, b = nombre.split("*")
        return rasgos.get(a, 0.0) * rasgos.get(b, 0.0)
    return rasgos.get(nombre, 0.0)


def _fila(rasgos, variables):
    return [_valor(rasgos, v) for v in variables]


@dataclass
class ModeloMirada:
    """Regresión por eje: pantalla = w0 + Σ wi · variable_i.

    vx / vy dicen qué variables usa cada eje (ver CANDIDATOS_MIRADA). Sin
    ellas es el modelo original: cabeza, iris y blendshapes del mismo eje.
    """
    wx: list
    wy: list
    vx: tuple = VARIABLES_POR_EJE["x"]
    vy: tuple = VARIABLES_POR_EJE["y"]

    def mapear(self, rasgos, limitar=True):
        def eje(pesos, variables):
            valor = pesos[0] + sum(w * v for w, v in zip(pesos[1:], _fila(rasgos, variables)))
            return min(max(valor, 0.0), 1.0) if limitar else valor
        return eje(self.wx, self.vx), eje(self.wy, self.vy)

    def como_dict(self):
        return {"wx": [float(w) for w in self.wx], "wy": [float(w) for w in self.wy],
                "vx": list(self.vx), "vy": list(self.vy)}

    @classmethod
    def desde_dict(cls, datos):
        """Restaura un modelo enviado por el cliente (p. ej. tras reconectar).
        Acepta también los de versiones anteriores: 3 o 4 pesos sin variables."""
        wx, wy = list(datos["wx"]), list(datos["wy"])
        pesos = [float(w) for w in (*wx, *wy)]
        if not all(math.isfinite(w) for w in pesos):
            raise ValueError("Pesos no válidos.")
        wx, wy = pesos[:len(wx)], pesos[len(wx):]
        if "vx" in datos or "vy" in datos:
            vx, vy = tuple(datos.get("vx") or ()), tuple(datos.get("vy") or ())
            if not set(vx) | set(vy) <= VARIABLES_VALIDAS:
                raise ValueError("Variables de mirada desconocidas.")
            if len(wx) != len(vx) + 1 or len(wy) != len(vy) + 1:
                raise ValueError("Cada eje necesita un peso por variable más el término independiente.")
            return cls(wx, wy, vx, vy)
        n = len(VARIABLES_POR_EJE["x"]) + 1
        if len(wx) != len(wy) or len(wx) not in (n - 1, n):
            raise ValueError(f"El modelo de mirada debe tener {n} pesos por eje.")
        relleno = [0.0] * (n - len(wx))
        return cls(wx + relleno, wy + relleno)


# Coordinación con la cabeza (para quien no puede usar los brazos): el cursor
# sigue solo el giro de la cabeza, sin los ojos, y llegar a las esquinas exige
# girar e inclinar el cuello. Es un ejercicio, no un atajo.
RANGO_CABEZA_X = 0.6   # giro: de esquina a esquina ≈ 30° a cada lado
RANGO_CABEZA_Y = 0.45  # inclinación hacia arriba y abajo, que cuesta más


def cursor_cabeza(rasgos, neutro):
    """neutro: (cabeza_x, cabeza_y) mirando al frente, medido al empezar."""
    u = 0.5 + (rasgos["cabeza_x"] - neutro[0]) / RANGO_CABEZA_X
    v = 0.5 + (rasgos["cabeza_y"] - neutro[1]) / RANGO_CABEZA_Y
    return min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)


def _filtrar_por_punto(muestras):
    """Descarta, punto por punto, las muestras que se alejan de las demás de
    ese punto (la mirada iba o venía, o un landmark saltó)."""
    grupos = {}
    for rasgos, punto in muestras:
        grupos.setdefault(tuple(punto), []).append(rasgos)
    buenas = []
    for punto, lista in grupos.items():
        datos = np.array([[r[c] for c in RASGOS_ROBUSTOS] for r in lista])
        mediana = np.median(datos, axis=0)
        mad = np.median(np.abs(datos - mediana), axis=0) * 1.4826
        # Piso del MAD: si casi no hay variación, no descartar por diferencias mínimas.
        mad = np.maximum(mad, 0.005)
        z = np.max(np.abs(datos - mediana) / mad, axis=1)
        orden = np.argsort(z)
        elegidas = [i for i in orden if z[i] <= LIMITE_MAD]
        if len(elegidas) < 3:
            elegidas = list(orden[:3])
        buenas += [(lista[i], punto) for i in sorted(elegidas)]
    return buenas


def _resolver(datos, variables, indice, regularizacion):
    """Ridge sobre variables estandarizadas; devuelve los pesos en unidades originales."""
    X = np.array([_fila(r, variables) for r, _ in datos], dtype=float)
    y = np.array([p[indice] for _, p in datos], dtype=float)
    media = X.mean(axis=0)
    escala = X.std(axis=0)
    escala[escala < 1e-9] = np.inf  # una variable que no cambia no aporta (peso 0)
    Z = (X - media) / escala
    n, k = Z.shape
    A = Z.T @ Z + np.eye(k) * regularizacion * n
    pesos = np.linalg.solve(A, Z.T @ (y - y.mean()))
    reales = pesos / escala
    return [float(y.mean() - reales @ media), *reales.tolist()]


def _ajustar(datos, vx, vy, regularizacion):
    return ModeloMirada(_resolver(datos, vx, 0, regularizacion), _resolver(datos, vy, 1, regularizacion),
                        tuple(vx), tuple(vy))


def _error(modelo, datos):
    return [math.hypot(*np.subtract(modelo.mapear(r), p)) for r, p in datos]


def _error_validacion(datos, vx, vy, regularizacion):
    """Error medio al predecir cada punto con un modelo ajustado sin él."""
    puntos = sorted({tuple(p) for _, p in datos})
    errores = []
    for punto in puntos:
        entrenar = [m for m in datos if tuple(m[1]) != punto]
        probar = [m for m in datos if tuple(m[1]) == punto]
        errores += _error(_ajustar(entrenar, vx, vy, regularizacion), probar)
    return float(np.mean(errores))


def ajustar_mirada(muestras) -> tuple:
    """muestras: lista de (rasgos, (x, y) del punto mirado).

    1. Descarta, en cada punto, las muestras sueltas (se movieron los ojos).
    2. Elige el modelo y la regularización que mejor predicen cada punto con
       un modelo ajustado sin ese punto (validación cruzada).
    3. Ajusta con todos los puntos y una segunda vez sin las muestras muy
       alejadas (la persona miró a otro lado o se distrajo un momento).

    Devuelve (modelo, error esperado en fracción de pantalla). El error es el
    de validación: lo que se equivoca en lugares que no se usaron al calibrar.
    """
    datos = _filtrar_por_punto(muestras)
    hay_validacion = len({tuple(p) for _, p in datos}) >= 6

    eleccion, error_validacion = None, None
    if hay_validacion:
        mejor_simple = None
        for nombre, vx, vy in CANDIDATOS_MIRADA:
            error, reg = min((_error_validacion(datos, vx, vy, reg), reg) for reg in REGULARIZACIONES)
            if mejor_simple is None or error < mejor_simple[0] * MEJORA_MINIMA:
                mejor_simple = (error, vx, vy, reg)
        error_validacion, vx, vy, reg = mejor_simple
        eleccion = (vx, vy, reg)
    else:
        eleccion = (VARIABLES_POR_EJE["x"], VARIABLES_POR_EJE["y"], REGULARIZACIONES[0])

    vx, vy, reg = eleccion
    modelo = _ajustar(datos, vx, vy, reg)
    errores = _error(modelo, datos)
    limite = max(2.5 * float(np.median(errores)), 0.05)
    buenas = [m for m, e in zip(datos, errores) if e <= limite]
    if len(buenas) >= max(12, len(vx) * 3) and len(buenas) < len(datos):
        modelo = _ajustar(buenas, vx, vy, reg)
        errores = _error(modelo, buenas)
    error = error_validacion if error_validacion is not None else float(np.mean(errores))
    return modelo, float(error)


class CorrectorDeriva:
    """Corrección implícita de la deriva de la mirada.

    Tras calibrar, la persona se acomoda en la silla o ladea la cabeza y el
    cursor se va corriendo siempre hacia el mismo lado. Cada vez que elige un
    botón por permanencia sabemos dónde estaba mirando (el botón), así que la
    diferencia entre ese botón y dónde estimamos la mirada corrige el sesgo,
    de a poco y con un tope, sin pedirle que vuelva a calibrar.
    """

    TASA = 0.4                 # cuánto del error de cada elección se corrige
    MAXIMO = 0.15              # corrección máxima por eje (fracción de pantalla)
    DISTANCIA_MAXIMA = 0.25    # más lejos que esto: no estaba mirando ese botón
    TAMANO_MAXIMO = 0.35       # objetivos más grandes no dicen dónde miraba

    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.dx = 0.0
        self.dy = 0.0
        self.observaciones = 0

    def corregir(self, x, y):
        return min(max(x + self.dx, 0.0), 1.0), min(max(y + self.dy, 0.0), 1.0)

    def observar(self, predicciones, objetivo, tamano=(0.0, 0.0)) -> bool:
        """predicciones: posiciones ya corregidas (sin filtrar) mientras miraba
        el objetivo; objetivo: centro del botón; tamano: su ancho y alto."""
        if not predicciones or max(tamano) > self.TAMANO_MAXIMO:
            return False
        mx = float(np.median([p[0] for p in predicciones]))
        my = float(np.median([p[1] for p in predicciones]))
        ex, ey = objetivo[0] - mx, objetivo[1] - my
        if math.hypot(ex, ey) > self.DISTANCIA_MAXIMA:
            return False
        self.dx = min(max(self.dx + self.TASA * ex, -self.MAXIMO), self.MAXIMO)
        self.dy = min(max(self.dy + self.TASA * ey, -self.MAXIMO), self.MAXIMO)
        self.observaciones += 1
        return True
