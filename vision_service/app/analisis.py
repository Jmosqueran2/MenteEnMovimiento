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


def zona_desde_hombros(hombro_izq, hombro_der, modo="seleccion") -> ZonaActiva:
    """Calibración: adapta la zona activa al cuerpo y a la distancia de la persona.

    Los hombros llegan normalizados (0–1). En modo coordinación la zona es más
    grande, así que para llegar a las esquinas hay que estirar los brazos.
    """
    alcance = ALCANCE.get(modo, ALCANCE["seleccion"])
    cx = (hombro_izq[0] + hombro_der[0]) / 2
    cy = (hombro_izq[1] + hombro_der[1]) / 2
    ancho = max(abs(hombro_izq[0] - hombro_der[0]), 0.05)

    medio_ancho = max(ancho * alcance, TAMANO_MINIMO_ZONA / 2)
    x0, x1 = cx - medio_ancho, cx + medio_ancho
    y0 = cy - ancho * alcance * 1.1     # hacia arriba: por encima de la cabeza
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
