"""Juegos de cada actividad y cómo se arma el plan de una sesión.

Cada sesión tiene 8 ítems que mezclan varios juegos de la misma actividad. La
receta (cuántos de cada juego) y la dificultad de cada juego dependen del
nivel de la persona.

Cada ítem del plan tiene un "modo", que define cómo se responde:
- "eleccion": se elige una opción (la mayoría de los juegos).
- "orden": se señalan las opciones en orden (secuencias y recuerdos).
- "parejas": se destapan cartas hasta encontrar todas las parejas.

Los juegos marcados con * reutilizan contenido del banco o de Mi Historia y
se arman al vuelo, sin filas propias en la base de datos.
"""

import random

from rest_framework.exceptions import ValidationError

from actividades.models import Juego, Pregunta
from historia.models import TipoContenido
from pacientes.models import TipoActividad

PREGUNTAS_POR_SESION = 8
MIN_CONTENIDOS_HISTORIA = 2

# Cuántos ítems de cada juego tiene una sesión, por actividad y nivel.
RECETAS = {
    TipoActividad.MEMORIA: {
        "facil": [("asociacion", 2), ("opuestos", 2), ("clasifica", 2), ("secuencia", 1), ("parejas", 1)],
        "medio": [("asociacion", 2), ("opuestos", 2), ("clasifica", 2), ("secuencia", 1), ("parejas", 1)],
        "dificil": [("asociacion", 2), ("opuestos", 2), ("clasifica", 1), ("secuencia", 2), ("parejas", 1)],
    },
    TipoActividad.ATENCION: {
        "facil": [("pareja_igual", 3), ("no_pertenece", 2), ("eleccion", 2), ("sigue_figura", 1)],
        "medio": [("pareja_igual", 2), ("no_pertenece", 2), ("eleccion", 2), ("sigue_figura", 2)],
        "dificil": [("pareja_igual", 2), ("no_pertenece", 2), ("eleccion", 1), ("sigue_figura", 3)],
    },
    TipoActividad.COORDINACION: {
        "facil": [("eleccion", 5), ("alcanza_recuerda", 3)],
        "medio": [("eleccion", 4), ("alcanza_recuerda", 4)],
        "dificil": [("eleccion", 4), ("alcanza_recuerda", 4)],
    },
}
# Mi Historia depende de lo que subió el cuidador: se alternan estos juegos.
# "Encuentra la foto igual" es el más fácil: no sale en Difícil.
JUEGOS_HISTORIA = {
    "facil": ["momento", "foto_igual", "quien_es"],
    "medio": ["momento", "quien_es", "foto_igual"],
    "dificil": ["momento", "quien_es"],
}

# Parámetros de dificultad de los juegos armados al vuelo.
PAREJAS = {  # pares de cartas; iguales o relacionadas (taza–cuchara); errores tolerados
    "facil": {"pares": 3, "relacionadas": False, "permitido": 4},
    "medio": {"pares": 4, "relacionadas": True, "permitido": 6},
    "dificil": {"pares": 6, "relacionadas": True, "permitido": 9},
}
SIGUE_FIGURA = {  # cartas, cuántas veces se cruzan y cuánto tarda cada cruce
    "facil": {"figuras": 3, "intercambios": 2, "paso_ms": 1600},
    "medio": {"figuras": 4, "intercambios": 4, "paso_ms": 1300},
    "dificil": {"figuras": 4, "intercambios": 6, "paso_ms": 1000},
}
ALCANZA_RECUERDA = {  # cuánto se ve el objeto; en Difícil hay que recordar su pareja
    "facil": {"memorizar_ms": 5000, "asociar": False},
    "medio": {"memorizar_ms": 3000, "asociar": False},
    "dificil": {"memorizar_ms": 3000, "asociar": True},
}
# El cursor con la mirada es menos preciso que la mano: con 12 cartas chicas
# costaría elegir bien, así que se juega con menos cartas y más grandes.
MAX_PARES_MIRADA = 4
OPCIONES_HISTORIA = {"facil": 2, "medio": 3, "dificil": 4}
RECUERDOS_A_ORDENAR = {"facil": 3, "medio": 3, "dificil": 4}


# --- Utilidades ----------------------------------------------------------------

def barajar(opciones, correcta):
    orden = list(range(len(opciones)))
    random.shuffle(orden)
    return [opciones[i] for i in orden], orden.index(correcta)


def barajar_orden(pasos):
    """Baraja los pasos y devuelve también el orden correcto como índices
    dentro de la lista barajada."""
    orden = list(range(len(pasos)))
    random.shuffle(orden)
    return [pasos[i] for i in orden], [orden.index(k) for k in range(len(pasos))]


def _item(juego, enunciado, opciones, correcta, pista, modo="eleccion", estimulo=None, ajustes=None,
          **extra):
    return {
        "juego": juego,
        "modo": modo,
        "enunciado": enunciado,
        "estimulo": estimulo or {"texto": "", "emoji": ""},
        "opciones": opciones,
        "correcta": correcta,
        "pista": pista,
        "ajustes": ajustes or {},
        **extra,
    }


def _preguntas(tipo, juego, nivel, cantidad, usadas):
    """Preguntas del banco para el nivel; si faltan, se completan con otros niveles."""
    base = Pregunta.objects.filter(tipo=tipo, juego=juego, activa=True).exclude(pk__in=usadas)
    elegidas = list(base.filter(nivel=nivel))
    random.shuffle(elegidas)
    if len(elegidas) < cantidad:
        otras = list(base.exclude(nivel=nivel))
        random.shuffle(otras)
        elegidas += otras
    elegidas = elegidas[:cantidad]
    usadas.update(p.pk for p in elegidas)
    return elegidas


def _de_pregunta(pregunta):
    if pregunta.juego == Juego.SECUENCIA:
        opciones, correcta = barajar_orden(pregunta.opciones)
        modo = "orden"
    else:
        opciones, correcta = barajar(pregunta.opciones, pregunta.respuesta_correcta)
        modo = "eleccion"
    return _item(pregunta.juego, pregunta.enunciado, opciones, correcta, pregunta.pista, modo=modo,
                 estimulo={"texto": pregunta.estimulo_texto, "emoji": pregunta.estimulo_emoji},
                 pregunta_id=pregunta.pk)


def _correcta(pregunta):
    return pregunta.opciones[pregunta.respuesta_correcta]


# --- Juegos armados al vuelo -----------------------------------------------------

def _parejas(nivel, usadas, puntero="mano"):
    """* Parejas de Memoria: cartas boca abajo que se destapan de a dos.
    Reutiliza los pares de Memoria (taza–cuchara, candado–llave…)."""
    ajustes = dict(PAREJAS[nivel])
    if puntero == "mirada" and ajustes["pares"] > MAX_PARES_MIRADA:
        # Menos pares: los errores tolerados bajan en la misma proporción.
        ajustes["permitido"] = round(ajustes["permitido"] * MAX_PARES_MIRADA / ajustes["pares"])
        ajustes["pares"] = MAX_PARES_MIRADA
    fuente = list(Pregunta.objects.filter(tipo=TipoActividad.MEMORIA, juego=Juego.ASOCIACION, activa=True))
    random.shuffle(fuente)
    pares, textos = [], set()
    for pregunta in fuente:
        a = {"texto": pregunta.estimulo_texto, "emoji": pregunta.estimulo_emoji}
        b = _correcta(pregunta)
        par = (a, b) if ajustes["relacionadas"] else (b, b)
        nombres = {par[0]["texto"], par[1]["texto"]}
        if not all(c["emoji"] for c in par) or nombres & textos:
            continue  # sin dibujo no se juega bien, y cada carta debe ser única
        textos |= nombres
        pares.append(par)
        if len(pares) == ajustes["pares"]:
            break
    cartas = [dict(carta, pareja=k) for k, par in enumerate(pares) for carta in par]
    random.shuffle(cartas)
    enunciado = "Encuentra las parejas que van juntas" if ajustes["relacionadas"] \
        else "Encuentra las cartas iguales"
    return _item("parejas", enunciado, cartas, None, "Recuerda dónde viste cada carta.", modo="parejas",
                 ajustes={"permitido": ajustes["permitido"], "pares": len(pares),
                          "relacionadas": ajustes["relacionadas"]})


def _sigue_figura(nivel, usadas):
    """* Atención sostenida: se muestran las figuras, se tapan y se cruzan
    despacio; hay que seguir con la vista dónde quedó la figura pedida.
    Reutiliza las figuras de Encuentra la pareja igual."""
    ajustes = SIGUE_FIGURA[nivel]
    pregunta = next(iter(_preguntas(TipoActividad.ATENCION, Juego.PAREJA_IGUAL, nivel, 1, usadas)), None)
    if pregunta is None:
        return None
    objetivo = {"texto": pregunta.estimulo_texto, "emoji": pregunta.estimulo_emoji}
    otras = [o for o in pregunta.opciones if o["texto"] != objetivo["texto"]][: ajustes["figuras"] - 1]
    opciones, correcta = barajar([objetivo, *otras], 0)
    return _item("sigue_figura", f"Sigue con la vista: {objetivo['texto']}", opciones, correcta,
                 "Mira solo esa carta mientras se mueve, sin perderla.", estimulo=objetivo,
                 ajustes={"intercambios": ajustes["intercambios"], "paso_ms": ajustes["paso_ms"],
                          "mostrar_ms": 2500})


def _alcanza_recuerda(nivel, usadas):
    """* Coordinación + Memoria: se muestra un objeto unos segundos, se oculta
    y hay que estirar el brazo hacia la respuesta. Reutiliza Memoria."""
    ajustes = ALCANZA_RECUERDA[nivel]
    pregunta = next(iter(_preguntas(TipoActividad.MEMORIA, Juego.ASOCIACION, nivel, 1, usadas)), None)
    if pregunta is None:
        return None
    if ajustes["asociar"]:
        recordar = {"texto": pregunta.estimulo_texto, "emoji": pregunta.estimulo_emoji}
        enunciado = "¿Qué objeto iba con lo que viste?"
    else:
        recordar = _correcta(pregunta)
        enunciado = "¿Cuál objeto viste?"
    opciones, correcta = barajar(pregunta.opciones, pregunta.respuesta_correcta)
    return _item("alcanza_recuerda", enunciado, opciones, correcta, pregunta.pista,
                 ajustes={"memorizar_ms": ajustes["memorizar_ms"], "recordar": recordar,
                          "enunciado_inicial": "Recuerda este objeto"})


def _plan_de_banco(paciente, tipo):
    nivel = paciente.nivel
    usadas = set()
    plan = []
    for juego, cantidad in RECETAS[tipo][nivel]:
        if juego == "parejas":
            plan += [_parejas(nivel, usadas, paciente.puntero) for _ in range(cantidad)]
        elif juego == "sigue_figura":
            plan += [_sigue_figura(nivel, usadas) for _ in range(cantidad)]
        elif juego == "alcanza_recuerda":
            plan += [_alcanza_recuerda(nivel, usadas) for _ in range(cantidad)]
        else:
            plan += [_de_pregunta(p) for p in _preguntas(tipo, juego, nivel, cantidad, usadas)]
    plan = [item for item in plan if item and item["opciones"]]

    # Si a algún juego le faltó contenido, se completa con preguntas de la actividad.
    if len(plan) < PREGUNTAS_POR_SESION:
        extra = Pregunta.objects.filter(tipo=tipo, activa=True).exclude(pk__in=usadas)
        extra = sorted(extra, key=lambda p: (p.nivel != nivel, random.random()))
        plan += [_de_pregunta(p) for p in extra[: PREGUNTAS_POR_SESION - len(plan)]]
    if not plan:
        raise ValidationError({"tipo": "Todavía no hay preguntas cargadas para esta actividad."})

    random.shuffle(plan)
    # Se empieza con una pregunta de elegir, la más sencilla de entender.
    primera = next((i for i, item in enumerate(plan) if item["juego"] in ("asociacion", "eleccion",
                                                                          "pareja_igual")), 0)
    plan.insert(0, plan.pop(primera))
    return plan[:PREGUNTAS_POR_SESION]


# --- Mi Historia ------------------------------------------------------------------

def _opciones_de_fotos(contenidos):
    """Opciones con la foto de cada contenido; el texto sirve para elegir con la voz."""
    return [{"texto": f"Foto {k + 1}", "emoji": "", "contenido_id": c.pk} for k, c in enumerate(contenidos)]


def _momento(contenido, todos, n):
    """¿Qué momento es este? Se ve la foto (o se oye el audio) y se elige el título."""
    otros = random.sample([c for c in todos if c.pk != contenido.pk], min(n - 1, len(todos) - 1))
    opciones = [{"texto": c.titulo, "emoji": ""} for c in [contenido, *otros]]
    opciones, correcta = barajar(opciones, 0)
    enunciado = "¿Qué momento es este?" if contenido.tipo == TipoContenido.IMAGEN \
        else "Escucha con atención. ¿Qué es?"
    return _item("momento", enunciado, opciones, correcta,
                 contenido.pista or "Tómate tu tiempo y recuerda.", contenido_id=contenido.pk)


def _quien_es(contenido, fotos, n):
    """* Mi Historia: ¿quién es? Se nombra el recuerdo y se señala su foto."""
    otras = random.sample([c for c in fotos if c.pk != contenido.pk], min(n - 1, len(fotos) - 1))
    grupo, correcta = barajar([contenido, *otras], 0)
    return _item("quien_es", f"¿En cuál foto está «{contenido.titulo}»?", _opciones_de_fotos(grupo),
                 correcta, contenido.pista or "Piensa en quién aparece en esa foto.")


def _foto_igual(contenido, fotos, n):
    """* Encuentra la pareja igual con las fotos de Mi Historia."""
    otras = random.sample([c for c in fotos if c.pk != contenido.pk], min(n - 1, len(fotos) - 1))
    grupo, correcta = barajar([contenido, *otras], 0)
    return _item("foto_igual", "Encuentra la misma foto", _opciones_de_fotos(grupo), correcta,
                 "Mira bien a las personas y los colores de la foto.", contenido_id=contenido.pk)


def _ordenar_recuerdos(contenidos, nivel):
    """* Mi Historia: ordena los recuerdos del más antiguo al más reciente.
    Solo con los que tienen año, y con años distintos para que no haya empate."""
    por_anio = {}
    for c in contenidos:
        if c.anio:
            por_anio.setdefault(c.anio, c)
    if len(por_anio) < 2:
        return None
    elegidos = random.sample(list(por_anio.values()), min(RECUERDOS_A_ORDENAR[nivel], len(por_anio)))
    elegidos.sort(key=lambda c: c.anio)
    pasos = [{"texto": c.titulo, "emoji": "" if c.tipo == TipoContenido.IMAGEN else "🎵",
              "contenido_id": c.pk if c.tipo == TipoContenido.IMAGEN else None} for c in elegidos]
    opciones, correcta = barajar_orden(pasos)
    return _item("ordenar_recuerdos", "Ordena los recuerdos: del más antiguo al más reciente", opciones,
                 correcta, f"El más antiguo es «{elegidos[0].titulo}».", modo="orden")


_JUEGOS_HISTORIA = {"momento": _momento, "quien_es": _quien_es, "foto_igual": _foto_igual}


def _plan_de_historia(paciente):
    nivel = paciente.nivel
    contenidos = list(paciente.contenidos.all())
    if len(contenidos) < MIN_CONTENIDOS_HISTORIA:
        raise ValidationError(
            {"tipo": "Mi Historia necesita al menos 2 fotos o audios. "
                     "Pide a tu cuidador que los agregue."}
        )
    fotos = [c for c in contenidos if c.tipo == TipoContenido.IMAGEN]
    n = OPCIONES_HISTORIA[nivel]
    juegos = [j for j in JUEGOS_HISTORIA[nivel] if j == "momento" or len(fotos) >= 2]

    # Una fila por juego con el contenido barajado; se intercalan para variar.
    filas = []
    for juego in juegos:
        candidatos = contenidos if juego == "momento" else fotos
        filas.append([(juego, c) for c in random.sample(candidatos, len(candidatos))])
    intercalados = [par for grupo in zip(*filas) for par in grupo] if filas else []
    sobrantes = [par for fila in filas for par in fila[min(map(len, filas)):]]
    plan = []
    ordenar = _ordenar_recuerdos(contenidos, nivel)
    if ordenar:
        plan.append(ordenar)
    # Cada recuerdo sale como mucho dos veces por sesión (además de ordenarlos), para no aburrir.
    limite = min(PREGUNTAS_POR_SESION, 2 * len(contenidos) + len(plan))
    for juego, contenido in intercalados + sobrantes:
        if len(plan) >= limite:
            break
        candidatos = contenidos if juego == "momento" else fotos
        plan.append(_JUEGOS_HISTORIA[juego](contenido, candidatos, n))
    random.shuffle(plan)
    return plan


def armar_plan(paciente, tipo):
    if tipo == TipoActividad.HISTORIA:
        return _plan_de_historia(paciente)
    return _plan_de_banco(paciente, tipo)
