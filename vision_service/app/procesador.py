"""Procesamiento de los frames de una conexión.

Privacidad: cada frame se decodifica, se analiza en memoria y se descarta.
Nunca se escribe en disco ni se reenvía; al cliente solo vuelven números.
"""

import math
import time
from collections import deque
from statistics import median

import cv2
import numpy as np

from . import analisis
from .filtros import FiltroOneEuro
from .modelos import imagen_mediapipe

LADOS = {"Left": "izquierda", "Right": "derecha"}
MUESTRAS_CALIBRACION = 10
# "voz": la persona elige hablando; la cámara solo vigila la postura (sin cursor).
PUNTEROS = ("mano", "mirada", "voz")
# Calibración de la mirada: en cada punto se esperan unos frames a que los ojos
# lleguen y se asienten, y luego se toman las muestras.
ESPERA_POR_PUNTO = 8
MUESTRAS_POR_PUNTO = 12
# Calibración guiada a la postura: en cada dirección hay que mover la mano al
# menos MOVIMIENTO_MINIMO_ALCANCE y luego dejarla quieta (dentro de QUIETO_RADIO)
# QUIETO_SEGUNDOS. Si en TIEMPO_MAXIMO_PASO no lo logra, se toma lo más lejos
# que llegó (o la estimación por los hombros si no se vio la mano).
MOVIMIENTO_MINIMO_ALCANCE = 0.05
QUIETO_RADIO = 0.03
QUIETO_SEGUNDOS = 1.2
TIEMPO_MAXIMO_PASO = 12.0
# Coordinación con la cabeza: frames mirando al frente para fijar la posición neutra.
MUESTRAS_NEUTRO_CABEZA = 10
# Apertura habitual de los ojos: percentil alto de los últimos frames (los
# parpadeos son cortos y quedan por debajo). Se mide en cada persona porque con
# párpados caídos el ojo abierto ya se ve "medio cerrado".
FRAMES_APERTURA = 90
MINIMO_APERTURA = 15
# Al elegir un botón con la mirada se usan las estimaciones de este lapso
# (segundos antes de elegir), sin las del último instante.
VENTANA_OBJETIVO_S = 0.9
MARGEN_OBJETIVO_S = 0.1
# Con poca luz se realza el contraste solo para buscar la cara (CLAHE).
LUZ_REALCE = 100


class ProcesadorSesion:
    def __init__(self, modelos):
        self.modelos = modelos
        self.detector_manos = modelos.nuevo_detector_manos()
        self.detector_rostro = None  # se crea al pedir el puntero con la mirada
        self.espejo = True
        self.modo = "seleccion"
        self.puntero = "mano"
        self.movilidad = "completa"
        self.zona = analisis.ZonaActiva()
        self.sensibilidad = analisis.SENSIBILIDAD_MINIMA
        self.filtro_x = FiltroOneEuro()
        self.filtro_y = FiltroOneEuro()
        # La mirada tiembla más que la mano: se suaviza más cuando está quieta.
        self.filtro_mirada_x = FiltroOneEuro(corte_minimo=0.3, beta=0.4)
        self.filtro_mirada_y = FiltroOneEuro(corte_minimo=0.3, beta=0.4)
        self.frames = 0
        self.ultimo_ts_ms = 0
        self.postura = None
        self.calibracion = {"estado": "pendiente", "progreso": 0.0}
        self._muestras = []
        # Alcance real de la mano medido en la calibración guiada (o None).
        self.alcance = None
        self._alcance_pedido = False
        self._paso_alcance = None
        self._valores_alcance = {}
        self.modelo_mirada = None
        self.calibracion_mirada = {"estado": "pendiente", "progreso": 0.0}
        self._muestras_mirada = []
        self._ultimo_cursor_mirada = None
        # Corrección implícita de la deriva: aprende de cada botón elegido con la mirada.
        self.corrector_mirada = analisis.CorrectorDeriva()
        self._recientes_mirada = deque(maxlen=60)  # (t, x, y) sin filtrar
        self._aperturas = deque(maxlen=FRAMES_APERTURA)
        # Postura al estar sentado: el navegador la activa durante las actividades.
        self.vigilar_postura = False
        self.monitor_postura = analisis.MonitorPostura()
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self._neutro_cabeza = None
        self._muestras_neutro = []

    def cerrar(self):
        self.detector_manos.close()
        if self.detector_rostro:
            self.detector_rostro.close()

    # --- Mensajes de control ---------------------------------------------------

    def configurar(self, mensaje: dict) -> dict:
        accion = mensaje.get("accion")
        if accion == "config":
            if "espejo" in mensaje:
                self.espejo = bool(mensaje["espejo"])
            if "sensibilidad" in mensaje:
                self.sensibilidad = analisis.limitar_sensibilidad(mensaje["sensibilidad"])
            if mensaje.get("movilidad") in analisis.MOVILIDADES:
                self.movilidad = mensaje["movilidad"]
                self._iniciar_calibracion()  # la zona depende de la movilidad
                self._asegurar_detector_rostro()
            if mensaje.get("modo") in analisis.ALCANCE:
                self.modo = mensaje["modo"]
                self._iniciar_calibracion()  # la zona depende del modo
                self._neutro_cabeza, self._muestras_neutro = None, []
            if mensaje.get("puntero") in PUNTEROS:
                error = self._cambiar_puntero(mensaje["puntero"])
                if error:
                    return error
            if "vigilar_postura" in mensaje:
                activa = bool(mensaje["vigilar_postura"])
                if activa and not self.vigilar_postura:
                    # Empiezan las actividades: se toma de nuevo su postura de referencia.
                    self.monitor_postura.reiniciar()
                self.vigilar_postura = activa
            if "modelo_mirada" in mensaje:
                try:
                    self.modelo_mirada = analisis.ModeloMirada.desde_dict(mensaje["modelo_mirada"])
                except (KeyError, TypeError, ValueError):
                    return {"tipo": "error", "detalle": "Modelo de mirada inválido."}
                self.calibracion_mirada = {"estado": "completa", "progreso": 1.0,
                                           "modelo": self.modelo_mirada.como_dict()}
                self.corrector_mirada.reiniciar()
            if "alcance" in mensaje:
                # El navegador restaura el alcance medido antes (p. ej. tras reconectar).
                if not analisis.alcance_valido(mensaje["alcance"]):
                    return {"tipo": "error", "detalle": "Alcance inválido."}
                self.alcance = {d: float(mensaje["alcance"][d]) for d, _ in analisis.DIRECCIONES_ALCANCE}
                self._alcance_pedido = False
                self._aplicar_alcance()
            if mensaje.get("alcance_guiado"):
                # Calibración guiada: primero los hombros, luego la mano hacia cada lado.
                self.alcance = None
                self._alcance_pedido = True
                self._iniciar_calibracion()
        elif accion == "omitir_alcance":
            if self.calibracion["estado"] == "alcance":
                self._alcance_pedido = False
                self._paso_alcance = None
                self.calibracion = {"estado": "completa", "progreso": 1.0,
                                    "zona": self.zona.como_dict(), "alcance_omitido": True}
        elif accion == "calibrar":
            self.alcance = None
            self._iniciar_calibracion()
            if self.puntero == "mirada":
                self._iniciar_calibracion_mirada()
        elif accion == "objetivo_mirada":
            return self._observar_objetivo(mensaje)
        else:
            return {"tipo": "error", "detalle": f"Acción desconocida: {accion!r}"}
        return {"tipo": "config", "espejo": self.espejo, "modo": self.modo,
                "puntero": self.puntero, "movilidad": self.movilidad,
                "sensibilidad": self.sensibilidad,
                "vigilar_postura": self.vigilar_postura,
                "mirada_disponible": self.modelos.mirada_disponible,
                "calibracion": self.calibracion, "calibracion_mirada": self.calibracion_mirada}

    def _observar_objetivo(self, mensaje):
        """El navegador avisa que se eligió un botón por permanencia con la
        mirada: {"punto": [x, y] centro del botón, "tamano": [ancho, alto]},
        todo en fracción de pantalla. Sirve para corregir la deriva."""
        try:
            x, y = (float(v) for v in mensaje["punto"])
            ancho, alto = (float(v) for v in mensaje.get("tamano", (0.0, 0.0)))
        except (KeyError, TypeError, ValueError):
            return {"tipo": "error", "detalle": "Objetivo de mirada inválido."}
        valores = (x, y, ancho, alto)
        if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in valores):
            return {"tipo": "error", "detalle": "Objetivo de mirada inválido."}
        aplicada = False
        if self.modelo_mirada and self.calibracion_mirada["estado"] == "completa":
            # Lo que se estimó mientras miraba el botón, sin el último instante
            # (la mirada ya puede estar yéndose a la pantalla siguiente).
            ahora = time.monotonic()
            recientes = [(u, v) for t, u, v in self._recientes_mirada
                         if ahora - VENTANA_OBJETIVO_S <= t <= ahora - MARGEN_OBJETIVO_S]
            aplicada = self.corrector_mirada.observar(recientes, (x, y), (ancho, alto))
        return {"tipo": "correccion_mirada", "aplicada": aplicada,
                "correccion": [round(self.corrector_mirada.dx, 4), round(self.corrector_mirada.dy, 4)]}

    def _cambiar_puntero(self, puntero):
        if puntero == "mirada" and not self.modelos.mirada_disponible:
            return {"tipo": "error", "detalle": "El cursor con la mirada no está disponible: "
                                                "falta el modelo face_landmarker.task."}
        self.puntero = puntero
        self._asegurar_detector_rostro()
        return None

    def _asegurar_detector_rostro(self):
        necesita = self.puntero == "mirada" or self.movilidad == "cabeza"
        if necesita and self.detector_rostro is None:
            self.detector_rostro = self.modelos.nuevo_detector_rostro()  # None si falta el modelo

    def _fuente_cursor(self):
        """Qué mueve el cursor ahora: "mano", "mirada", "cabeza" o None (con la voz no hay cursor)."""
        if self.puntero == "voz":
            return None
        if self.modo == "coordinacion":
            # El ejercicio es moverse: con los brazos o, si no se puede, con la cabeza.
            return "cabeza" if self.movilidad == "cabeza" and self.detector_rostro else "mano"
        return "mirada" if self.puntero == "mirada" else "mano"

    def _iniciar_calibracion(self):
        self._muestras = []
        self._paso_alcance = None
        if self.alcance and not self._alcance_pedido:
            # Ya se midió el alcance real: al cambiar de modo o de movilidad
            # solo se recalcula la zona, sin volver a pedir los movimientos.
            self._aplicar_alcance()
            return
        self.calibracion = {"estado": "en_progreso", "progreso": 0.0}

    def _aplicar_alcance(self):
        self.zona = analisis.zona_desde_alcance(self.alcance, self.modo)
        self.calibracion = {"estado": "completa", "progreso": 1.0, "zona": self.zona.como_dict(),
                            "alcance": {d: round(v, 4) for d, v in self.alcance.items()}}

    # --- Calibración guiada a la postura: la mano hacia cada lado ---------------

    def _iniciar_paso_alcance(self, indice, t):
        if indice == 0:
            self._valores_alcance = {}
        self._paso_alcance = {"indice": indice, "inicio": t, "origen": None,
                              "extremo": None, "ancla": None, "desde": t}
        direccion, objetivo = analisis.DIRECCIONES_ALCANCE[indice]
        total = len(analisis.DIRECCIONES_ALCANCE)
        self.calibracion = {"estado": "alcance", "progreso": round(indice / total, 2),
                            "paso": indice, "total": total, "direccion": direccion,
                            "objetivo": list(objetivo), "quieto": 0.0, "mano": False}

    def _actualizar_alcance(self, palma, t):
        if self.calibracion["estado"] != "alcance" or self._paso_alcance is None:
            return
        paso = self._paso_alcance
        direccion, _ = analisis.DIRECCIONES_ALCANCE[paso["indice"]]
        eje = 1 if direccion in ("arriba", "abajo") else 0
        signo = -1 if direccion in ("arriba", "izquierda") else 1
        quieto = 0.0
        if palma is not None:
            valor = palma[eje]
            if paso["origen"] is None:
                paso["origen"] = valor
            if paso["extremo"] is None or (valor - paso["extremo"]) * signo > 0:
                paso["extremo"] = valor
            ancla = paso["ancla"]
            if ancla is None or math.hypot(palma[0] - ancla[0], palma[1] - ancla[1]) > QUIETO_RADIO:
                paso["ancla"], paso["desde"] = palma, t
            # Solo cuenta quedarse quieto después de haberse movido hacia ese lado:
            # si no, la mano en reposo completaría el paso sola.
            if (valor - paso["origen"]) * signo >= MOVIMIENTO_MINIMO_ALCANCE:
                quieto = min((t - paso["desde"]) / QUIETO_SEGUNDOS, 1.0)
                if quieto >= 1.0:
                    self._cerrar_paso_alcance(valor, t)
                    return
        else:
            paso["ancla"] = None
        if t - paso["inicio"] >= TIEMPO_MAXIMO_PASO:
            self._cerrar_paso_alcance(paso["extremo"], t)
            return
        total = len(analisis.DIRECCIONES_ALCANCE)
        self.calibracion.update(quieto=round(quieto, 2), mano=palma is not None,
                                progreso=round((paso["indice"] + quieto) / total, 2))

    def _cerrar_paso_alcance(self, valor, t):
        direccion, _ = analisis.DIRECCIONES_ALCANCE[self._paso_alcance["indice"]]
        self._valores_alcance[direccion] = valor
        siguiente = self._paso_alcance["indice"] + 1
        if siguiente < len(analisis.DIRECCIONES_ALCANCE):
            self._iniciar_paso_alcance(siguiente, t)
            return
        # Si en algún lado no se vio la mano, se usa la estimación por los hombros.
        estimada = {"arriba": self.zona.y0, "abajo": self.zona.y1,
                    "izquierda": self.zona.x0, "derecha": self.zona.x1}
        self.alcance = {d: v if v is not None else estimada[d] for d, v in
                        ((d, self._valores_alcance.get(d)) for d, _ in analisis.DIRECCIONES_ALCANCE)}
        self._alcance_pedido = False
        self._paso_alcance = None
        self._aplicar_alcance()

    def _actualizar_calibracion(self, postura):
        if self.calibracion["estado"] in ("completa", "alcance") or not postura or not postura.get("hombros"):
            return
        if self.calibracion["estado"] == "pendiente":
            self._iniciar_calibracion()  # calibración automática la primera vez
        self._muestras.append(postura["hombros"])
        self.calibracion["progreso"] = round(len(self._muestras) / MUESTRAS_CALIBRACION, 2)
        if len(self._muestras) >= MUESTRAS_CALIBRACION:
            def mediana(lado, eje):
                return median(m[lado][eje] for m in self._muestras)
            self.zona = analisis.zona_desde_hombros(
                (mediana("izquierdo", 0), mediana("izquierdo", 1)),
                (mediana("derecho", 0), mediana("derecho", 1)),
                self.modo,
                self.movilidad,
            )
            if self._alcance_pedido:
                # La zona por hombros queda como provisoria (mueve el cursor de
                # ayuda) mientras se mide el alcance real.
                self._iniciar_paso_alcance(0, time.monotonic())
            else:
                self.calibracion = {"estado": "completa", "progreso": 1.0,
                                    "zona": self.zona.como_dict()}

    # --- Calibración de la mirada: la persona mira 5 puntos de la pantalla ------

    def _iniciar_calibracion_mirada(self):
        self.corrector_mirada.reiniciar()
        self._recientes_mirada.clear()
        self._muestras_mirada = []
        self._indice_mirada = 0
        self._frames_en_punto = 0
        self._muestras_punto = 0
        self.calibracion_mirada = {"estado": "en_progreso", "progreso": 0.0, "indice": 0,
                                   "total": len(analisis.PUNTOS_CALIBRACION_MIRADA),
                                   "punto": list(analisis.PUNTOS_CALIBRACION_MIRADA[0])}

    def _actualizar_calibracion_mirada(self, rasgos):
        if self.calibracion_mirada["estado"] == "completa" or not rasgos:
            return
        if self.calibracion_mirada["estado"] == "pendiente":
            self._iniciar_calibracion_mirada()  # empieza sola al ver la cara
        if not rasgos["ojos_abiertos"]:
            return  # un parpadeo no cuenta como muestra

        self._frames_en_punto += 1
        if self._frames_en_punto <= ESPERA_POR_PUNTO:
            return
        puntos = analisis.PUNTOS_CALIBRACION_MIRADA
        self._muestras_mirada.append((rasgos, puntos[self._indice_mirada]))
        self._muestras_punto += 1

        if self._muestras_punto >= MUESTRAS_POR_PUNTO:
            self._indice_mirada += 1
            self._frames_en_punto = 0
            self._muestras_punto = 0
            if self._indice_mirada >= len(puntos):
                self.modelo_mirada, error = analisis.ajustar_mirada(self._muestras_mirada)
                self.calibracion_mirada = {"estado": "completa", "progreso": 1.0,
                                           "error": round(error, 3),
                                           "modelo": self.modelo_mirada.como_dict()}
                return
            self.calibracion_mirada["indice"] = self._indice_mirada
            self.calibracion_mirada["punto"] = list(puntos[self._indice_mirada])

        avance = self._indice_mirada + self._muestras_punto / MUESTRAS_POR_PUNTO
        self.calibracion_mirada["progreso"] = round(avance / len(puntos), 2)

    # --- Frames ---------------------------------------------------------------

    def procesar(self, jpeg: bytes) -> dict:
        inicio = time.perf_counter()
        imagen = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if imagen is None:
            return {"tipo": "error", "detalle": "El frame no es un JPEG válido."}
        if self.espejo:
            imagen = cv2.flip(imagen, 1)
        alto, ancho = imagen.shape[:2]
        self.frames += 1
        # MediaPipe en modo VIDEO exige marcas de tiempo estrictamente crecientes.
        ts = max(int(time.monotonic() * 1000), self.ultimo_ts_ms + 1)
        self.ultimo_ts_ms = ts
        rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)

        luz = analisis.medir_luz(cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY))
        fuente = self._fuente_cursor()
        mano = self._detectar_mano(rgb, ts, ancho, alto) if fuente == "mano" else None
        rostro = self._detectar_rostro(rgb, ts, ancho, alto, luz) if self.detector_rostro else None

        if (self.frames - 1) % self.modelos.config.pose_cada_n_frames == 0:
            puntos = self.modelos.detectar_pose(imagen)
            self.postura = analisis.analizar_postura(puntos, ancho, alto) if puntos \
                else {"persona": False}
            self._actualizar_calibracion(self.postura)
            if self.vigilar_postura:
                if self.modo == "coordinacion":
                    self.monitor_postura.pausar()
                else:
                    self.monitor_postura.actualizar(self.postura.get("medidas"), time.monotonic())

        if self.puntero == "mirada":
            self._actualizar_calibracion_mirada(rostro)
        self._actualizar_alcance(mano.get("_palma") if mano else None, time.monotonic())
        if fuente == "mirada":
            cursor = self._cursor_mirada(rostro)
        elif fuente == "cabeza":
            cursor = self._cursor_cabeza(rostro)
        else:
            cursor = self._cursor_mano(mano)

        postura_publica = {k: v for k, v in self.postura.items() if k != "hombros"}
        respuesta = {
            "tipo": "estado",
            "frame": self.frames,
            "ms": round((time.perf_counter() - inicio) * 1000),
            "cursor": cursor,
            "mano": mano,
            "luz": luz,
            "postura": postura_publica,
            "calibracion": self.calibracion,
            "alertas": analisis.alertas(luz, self.postura),
            # "midiendo" | "buena" | "encorvado" | "inclinado" | "pausa" (Coordinación), o None si no se vigila.
            "postura_sentado": (None if not self.vigilar_postura
                                else "pausa" if self.modo == "coordinacion" else self.monitor_postura.estado),
        }
        if self.detector_rostro:
            respuesta["rostro"] = {"detectado": bool(rostro),
                                   "ojos_abiertos": bool(rostro and rostro["ojos_abiertos"]),
                                   "apertura": round(rostro["apertura"], 3) if rostro else None}
            respuesta["calibracion_mirada"] = self.calibracion_mirada
        return respuesta

    def _cursor_mano(self, mano):
        if not mano:
            self.filtro_x.reiniciar()
            self.filtro_y.reiniciar()
            return None
        u, v = self.zona.escalada(self.sensibilidad).mapear(*mano.pop("_palma"))
        t = time.monotonic()
        return {"x": round(self.filtro_x(u, t), 4), "y": round(self.filtro_y(v, t), 4),
                "fuente": "mano"}

    def _cursor_mirada(self, rostro):
        if not rostro or not self.modelo_mirada or self.calibracion_mirada["estado"] != "completa":
            self.filtro_mirada_x.reiniciar()
            self.filtro_mirada_y.reiniciar()
            self._ultimo_cursor_mirada = None
            return None
        if not rostro["ojos_abiertos"]:
            # Al parpadear el iris se tapa y el cursor saltaría hacia abajo:
            # se deja quieto donde estaba, así tampoco se pierde la permanencia.
            return self._ultimo_cursor_mirada
        u, v = self.corrector_mirada.corregir(*self.modelo_mirada.mapear(rostro, limitar=False))
        t = time.monotonic()
        self._recientes_mirada.append((t, u, v))
        self._ultimo_cursor_mirada = {"x": round(self.filtro_mirada_x(u, t), 4),
                                      "y": round(self.filtro_mirada_y(v, t), 4),
                                      "fuente": "mirada"}
        return self._ultimo_cursor_mirada

    def _cursor_cabeza(self, rostro):
        if not rostro:
            self.filtro_mirada_x.reiniciar()
            self.filtro_mirada_y.reiniciar()
            return None
        if self._neutro_cabeza is None:
            # Al empezar la actividad la persona mira la pregunta, al frente.
            self._muestras_neutro.append((rostro["cabeza_x"], rostro["cabeza_y"]))
            if len(self._muestras_neutro) < MUESTRAS_NEUTRO_CABEZA:
                return None
            self._neutro_cabeza = (median(m[0] for m in self._muestras_neutro),
                                   median(m[1] for m in self._muestras_neutro))
        u, v = analisis.cursor_cabeza(rostro, self._neutro_cabeza)
        t = time.monotonic()
        return {"x": round(self.filtro_mirada_x(u, t), 4), "y": round(self.filtro_mirada_y(v, t), 4),
                "fuente": "cabeza"}

    def _detectar_mano(self, rgb, ts, ancho, alto):
        resultado = self.detector_manos.detect_for_video(imagen_mediapipe(rgb), ts)
        if not resultado.hand_landmarks:
            return None

        puntos = resultado.hand_landmarks[0]
        normalizados = [(p.x, p.y) for p in puntos]
        en_pixeles = [(p.x * ancho, p.y * alto) for p in puntos]
        lado = resultado.handedness[0][0].category_name if resultado.handedness else None
        return {
            "detectada": True,
            "gesto": analisis.clasificar_gesto(en_pixeles),
            "lado": LADOS.get(lado, lado),
            "_palma": analisis.centro_palma(normalizados),
        }

    def _realzar(self, rgb):
        """Ecualiza el brillo por zonas: con poca luz los ojos quedan en sombra
        y el detector de iris pierde el borde."""
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        lab[:, :, 0] = self._clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    def _detectar_rostro(self, rgb, ts, ancho, alto, luz):
        if luz["nivel"] < LUZ_REALCE or luz["estado"] == "contraluz":
            rgb = self._realzar(rgb)
        resultado = self.detector_rostro.detect_for_video(imagen_mediapipe(rgb), ts)
        if not resultado.face_landmarks or len(resultado.face_landmarks[0]) < 478:
            return None
        blendshapes = None
        if resultado.face_blendshapes:
            blendshapes = {c.category_name: c.score for c in resultado.face_blendshapes[0]}
        habitual = None
        if len(self._aperturas) >= MINIMO_APERTURA:
            habitual = float(np.percentile(self._aperturas, 80))
        rasgos = analisis.rasgos_mirada([(p.x * ancho, p.y * alto) for p in resultado.face_landmarks[0]],
                                        blendshapes, habitual)
        self._aperturas.append(rasgos["apertura"])
        return rasgos
