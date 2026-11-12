"""Informe de seguimiento en PDF (pantalla 15): resumen, gráfica de aciertos
por sesión y la tabla completa de sesiones del periodo."""

from io import BytesIO

from django.utils import timezone
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Colores de la guía de estilo (estilos.css).
NOCHE = colors.HexColor("#081c15")
VERDE = colors.HexColor("#03735a")
MENTA = colors.HexColor("#ddefe8")
GRIS = colors.HexColor("#3e4e48")
BORDE = colors.HexColor("#c9d6d0")


NOMBRE_PUNTERO = {"mano": "La mano", "mirada": "La mirada", "cabeza": "La cabeza", "voz": "La voz",
                  "mouse": "Mouse (pruebas)"}


def _decimal(numero):
    return "—" if numero is None else f"{numero:.1f}".replace(".", ",")


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Title"], textColor=NOCHE, fontSize=20, spaceAfter=4),
        "subtitulo": ParagraphStyle("subtitulo", parent=base["Normal"], textColor=GRIS, fontSize=10,
                                    alignment=TA_CENTER, spaceAfter=14),
        "seccion": ParagraphStyle("seccion", parent=base["Heading2"], textColor=NOCHE, fontSize=13,
                                  spaceBefore=14, spaceAfter=6),
        "normal": ParagraphStyle("normal", parent=base["Normal"], textColor=NOCHE, fontSize=10),
        "pie": ParagraphStyle("pie", parent=base["Normal"], textColor=GRIS, fontSize=8),
    }


def _cifras(resumen):
    valores = [
        (f"{resumen['tasa_aciertos']} %" if resumen["tasa_aciertos"] is not None else "—", "Aciertos"),
        (f"{_decimal(resumen['tiempo_promedio_s'])} s", "Tiempo medio de respuesta"),
        (str(resumen["sesiones"]), "Sesiones"),
        (resumen["nivel_texto"], "Nivel actual"),
    ]
    celdas = [[Paragraph(f"<font size=16><b>{v}</b></font><br/><font size=8 color='#3e4e48'>{e}</font>")
               for v, e in valores]]
    tabla = Table(celdas, colWidths=[4.2 * cm] * 4)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MENTA),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tabla


def _grafica(sesiones):
    """Porcentaje de aciertos de las últimas 15 sesiones."""
    ultimas = sesiones[-15:]
    dibujo = Drawing(16.8 * cm, 6 * cm)
    grafica = VerticalBarChart()
    grafica.x, grafica.y = 1.2 * cm, 1 * cm
    grafica.width, grafica.height = 15 * cm, 4.4 * cm
    grafica.data = [[s.tasa_aciertos or 0 for s in ultimas]]
    grafica.categoryAxis.categoryNames = [timezone.localtime(s.fin).strftime("%d/%m") for s in ultimas]
    grafica.categoryAxis.labels.fontSize = 7
    grafica.categoryAxis.strokeColor = BORDE
    grafica.valueAxis.valueMin, grafica.valueAxis.valueMax, grafica.valueAxis.valueStep = 0, 100, 25
    grafica.valueAxis.labels.fontSize = 7
    grafica.valueAxis.labelTextFormat = "%d %%"
    grafica.valueAxis.strokeColor = BORDE
    grafica.valueAxis.gridStrokeColor = BORDE
    grafica.valueAxis.visibleGrid = True
    grafica.bars[0].fillColor = VERDE
    grafica.bars[0].strokeColor = None
    grafica.barLabelFormat = "%d"
    grafica.barLabels.fontSize = 7
    grafica.barLabels.nudge = 6
    dibujo.add(grafica)
    if len(ultimas) < len(sesiones):
        dibujo.add(String(1.2 * cm, 0.1 * cm, f"Últimas {len(ultimas)} de {len(sesiones)} sesiones",
                          fontSize=7, fillColor=GRIS))
    return dibujo


def _tabla_sesiones(sesiones, estilos):
    from sesiones.servicios import resumen_observado

    pedidos = list(sesiones[0].paciente.pedidos_ayuda.all()) if sesiones else []
    chico = ParagraphStyle("chico", parent=estilos["normal"], fontSize=7.5, leading=9)
    filas = [["Fecha", "Actividad", "Nivel", "Aciertos", "%", "Tiempo", "La IA observó"]]
    for s in reversed(sesiones):
        filas.append([
            timezone.localtime(s.fin).strftime("%d/%m/%Y %H:%M"),
            s.get_tipo_display(),
            s.get_nivel_display(),
            f"{s.aciertos} de {s.total_preguntas}",
            f"{s.tasa_aciertos} %" if s.tasa_aciertos is not None else "—",
            f"{_decimal(s.tiempo_promedio_s)} s",
            Paragraph(_texto_observado(resumen_observado(s, pedidos)), chico),
        ])
    tabla = Table(filas, repeatRows=1,
                  colWidths=[2.8 * cm, 2.4 * cm, 1.6 * cm, 1.8 * cm, 1.3 * cm, 1.5 * cm, 5.4 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NOCHE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ebf2fa")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, BORDE),
        ("ALIGN", (3, 0), (5, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabla


def _texto_observado(ia):
    partes = []
    if ia["postura_vigilada"]:
        avisos = ia["avisos_postura"]
        partes.append("postura bien" if avisos == 0 else f"{avisos} aviso{'s' if avisos != 1 else ''} de postura")
    if ia["pedidos_ayuda"]:
        partes.append(f"pidió ayuda {ia['pedidos_ayuda']} vez" + ("es" if ia["pedidos_ayuda"] != 1 else ""))
    if ia["error_mirada"] is not None:
        partes.append(f"mirada ±{_decimal(100 * ia['error_mirada'])} %")
    return " · ".join(partes) or "—"


def _seccion_ia(resumen, sesiones, e):
    """Lo que observó la IA de visión: totales del periodo y una fila por sesión."""
    ia = resumen.get("ia") or {}
    if not ia.get("sesiones_con_datos"):
        return [Paragraph("Lo que observó la IA", e["seccion"]),
                Paragraph("Todavía no hay sesiones con datos de la cámara en este periodo.", e["normal"])]
    postura = (f"{ia['avisos_postura']} avisos en {ia['sesiones_postura']} sesiones "
               f"({ia['sesiones_sin_avisos']} sin ningún aviso)") if ia["sesiones_postura"] else "no se vigiló"
    filas_resumen = [
        ["Postura al estar sentada", postura],
        ["Tiempo con mala postura", f"{_decimal(ia['minutos_mala_postura'])} min" if ia["sesiones_postura"] else "—"],
        ["Pedidos de ayuda", str(ia["pedidos_ayuda"])],
        ["Cursor", ", ".join(f"{NOMBRE_PUNTERO.get(p, p)} ({n})" for p, n in ia["punteros"].items()) or "—"],
    ]
    if ia["error_mirada"] is not None:
        filas_resumen.append(["Precisión de la mirada", f"±{_decimal(100 * ia['error_mirada'])} % de la pantalla · "
                                                         f"{ia['correcciones_mirada']} ajustes automáticos"])
    if ia["imagenes_analizadas"]:
        ms = f" · {ia['ms_por_imagen']} ms por imagen" if ia["ms_por_imagen"] else ""
        filas_resumen.append(["Imágenes analizadas", f"{ia['imagenes_analizadas']:,}".replace(",", ".") + ms])
    tabla = Table([[Paragraph(f"<b>{a}</b>", e["normal"]), Paragraph(b, e["normal"])] for a, b in filas_resumen],
                  colWidths=[5 * cm, 11.8 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), MENTA),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [
        Paragraph("Lo que observó la IA", e["seccion"]),
        Paragraph("La cámara analiza cada imagen y la descarta al instante: no se graba nada. "
                  "Estos datos los calcula la IA de visión durante cada actividad.", e["pie"]),
        Spacer(1, 0.2 * cm),
        tabla,
    ]


def generar(paciente, sesiones, resumen, dias):
    """Devuelve los bytes del PDF. `sesiones` en orden cronológico."""
    salida = BytesIO()
    nombre = str(paciente)
    hoy = timezone.localdate()
    doc = SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title=f"Seguimiento de {nombre}", author="Mente en Movimiento",
    )
    e = _estilos()
    periodo = "el último año" if dias >= 365 else f"los últimos {dias} días"
    edad = f" · {paciente.edad} años" if paciente.edad is not None else ""

    contenido = [
        Paragraph(f"Seguimiento de {nombre}", e["titulo"]),
        Paragraph(f"Mente en Movimiento · {periodo}{edad} · generado el {hoy.strftime('%d/%m/%Y')}", e["subtitulo"]),
    ]
    if not sesiones:
        contenido.append(Paragraph("Aún no hay sesiones registradas en este periodo.", e["normal"]))
    else:
        contenido += [
            _cifras(resumen),
            Paragraph("Aciertos por sesión", e["seccion"]),
            _grafica(sesiones),
            Paragraph("Sesiones del periodo", e["seccion"]),
            _tabla_sesiones(sesiones, e),
            *_seccion_ia(resumen, sesiones, e),
        ]
    contenido += [
        Spacer(1, 0.6 * cm),
        Paragraph("Acierto: pregunta resuelta en el primer intento. El nivel se ajusta solo después de cada "
                  "actividad; el cuidador puede cambiarlo en el panel.", e["pie"]),
    ]

    def numerar(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GRIS)
        canvas.drawRightString(A4[0] - 2 * cm, 1 * cm, f"Página {documento.page}")
        canvas.drawString(2 * cm, 1 * cm, f"Seguimiento de {nombre}")
        canvas.restoreState()

    doc.build(contenido, onFirstPage=numerar, onLaterPages=numerar)
    return salida.getvalue()
