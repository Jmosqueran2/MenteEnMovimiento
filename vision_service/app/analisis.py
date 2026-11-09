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

    def como_dict(self):
        return {k: round(v, 3) for k, v in asdict(self).items()}


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

    for lado, (h, c, m) in {"izquierdo": (HOMBRO_IZQ, CODO_IZQ, MUNECA_IZQ),
                            "derecho": (HOMBRO_DER, CODO_DER, MUNECA_DER)}.items():
        if visible(h) and visible(c) and visible(m):
            grados = angulo(puntos[h][:2], puntos[c][:2], puntos[m][:2])
            resultado["brazos"][lado] = {
                "angulo_codo": round(grados),
                "extendido": grados >= ANGULO_BRAZO_EXTENDIDO,
                "levantado": puntos[m][1] < puntos[h][1],
            }
    return resultado


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

OJOS = (  # (esquina, esquina, párpado superior, párpado inferior, centro del iris)
    (33, 133, 159, 145, 468),
    (362, 263, 386, 374, 473),
)
PUNTA_NARIZ = 1
OJO_CERRADO = 0.12  # alto / ancho del ojo por debajo del cual se considera parpadeo

# Dónde aparece el punto que la persona debe mirar al calibrar (0–1 de la pantalla).
PUNTOS_CALIBRACION_MIRADA = ((0.5, 0.5), (0.12, 0.15), (0.88, 0.15), (0.88, 0.85), (0.12, 0.85))
REGULARIZACION = 1e-4


def rasgos_mirada(puntos) -> dict:
    """puntos: 478 × (x_px, y_px). Las medidas se dividen por el tamaño de la
    cara, así no cambian si la persona se acerca, se aleja o se corre de lado."""
    centros, iris_x, iris_y, aperturas = [], [], [], []
    for a, b, sup, inf, iris in OJOS:
        ancho = _dist(puntos[a], puntos[b]) or 1.0
        cx = (puntos[a][0] + puntos[b][0]) / 2
        cy = (puntos[a][1] + puntos[b][1]) / 2
        centros.append((cx, cy))
        iris_x.append((puntos[iris][0] - cx) / ancho)
        iris_y.append((puntos[iris][1] - (puntos[sup][1] + puntos[inf][1]) / 2) / ancho)
        aperturas.append(_dist(puntos[sup], puntos[inf]) / ancho)

    entre_ojos = _dist(*centros) or 1.0
    medio = ((centros[0][0] + centros[1][0]) / 2, (centros[0][1] + centros[1][1]) / 2)
    nariz = puntos[PUNTA_NARIZ]
    apertura = sum(aperturas) / 2
    return {
        "cabeza_x": (nariz[0] - medio[0]) / entre_ojos,
        "cabeza_y": (nariz[1] - medio[1]) / entre_ojos,
        "iris_x": sum(iris_x) / 2,
        "iris_y": sum(iris_y) / 2,
        "apertura": apertura,
        "ojos_abiertos": apertura >= OJO_CERRADO,
    }


def _variables(rasgos, eje):
    return [1.0, rasgos[f"cabeza_{eje}"], rasgos[f"iris_{eje}"]]


@dataclass
class ModeloMirada:
    """Regresión lineal por eje: pantalla = w0 + w1·cabeza + w2·iris."""
    wx: list
    wy: list

    def mapear(self, rasgos):
        def eje(pesos, nombre):
            valor = sum(w * v for w, v in zip(pesos, _variables(rasgos, nombre)))
            return min(max(valor, 0.0), 1.0)
        return eje(self.wx, "x"), eje(self.wy, "y")

    def como_dict(self):
        return {"wx": [float(w) for w in self.wx], "wy": [float(w) for w in self.wy]}

    @classmethod
    def desde_dict(cls, datos):
        """Restaura un modelo enviado por el cliente (p. ej. tras reconectar)."""
        wx, wy = datos["wx"], datos["wy"]
        if len(wx) != 3 or len(wy) != 3:
            raise ValueError("El modelo de mirada debe tener 3 pesos por eje.")
        pesos = [float(w) for w in (*wx, *wy)]
        if not all(math.isfinite(w) for w in pesos):
            raise ValueError("Pesos no válidos.")
        return cls(pesos[:3], pesos[3:])


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


def ajustar_mirada(muestras) -> tuple:
    """muestras: lista de (rasgos, (x, y) del punto mirado).

    Mínimos cuadrados con una regularización pequeña (ridge): si la persona solo
    movió los ojos y no la cabeza, esa variable no aporta y su peso queda en ~0
    en vez de dispararse. Devuelve (modelo, error medio en fracción de pantalla).
    """
    def resolver(eje, indice):
        X = np.array([_variables(r, eje) for r, _ in muestras])
        y = np.array([p[indice] for _, p in muestras])
        penalizacion = np.eye(3) * REGULARIZACION * len(muestras)
        penalizacion[0, 0] = 0.0  # el término independiente no se penaliza
        return np.linalg.solve(X.T @ X + penalizacion, X.T @ y).tolist()

    modelo = ModeloMirada(resolver("x", 0), resolver("y", 1))
    errores = [math.hypot(*(np.subtract(modelo.mapear(r), p))) for r, p in muestras]
    return modelo, float(np.mean(errores))
