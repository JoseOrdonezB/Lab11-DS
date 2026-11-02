"""Genera las páginas 5–8 del informe técnico y las anexa al PDF base de las secciones 1–4.

Uso:
    python scripts/generar_informe_pdf.py

Entradas:
    docs/informe_secciones_5_8.md   (contenido de las secciones 5–8)
    docs/informe_base_1_4.pdf       (copia del informe original de las secciones 1–4)
Salida:
    Lab11.pdf                       (base + secciones 5–8)
"""
from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Preformatted, Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parent.parent
FUENTE_MD = RAIZ / "docs" / "informe_secciones_5_8.md"
BASE_PDF = RAIZ / "docs" / "informe_base_1_4.pdf"
NUEVO_PDF = RAIZ / "docs" / "_secciones_5_8.pdf"
SALIDA = RAIZ / "Lab11.pdf"

AZUL = colors.HexColor("#1B2A41")
PIZARRA = colors.HexColor("#5C6B7A")
GRIS = colors.HexColor("#E6EBF0")

ANCHO, ALTO = A4
MARGEN = 2.0 * cm
ANCHO_UTIL = ANCHO - 2 * MARGEN


def _inline(texto):
    """Escapa HTML y convierte **negrita** y `código` a marcado de ReportLab."""
    t = (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<font name="Courier">\1</font>', t)
    return t


def _tabla(filas, estilos):
    """Convierte filas markdown en una Table con anchos proporcionales al contenido."""
    cabecera = filas[0]
    cuerpo = filas[1:]
    ncols = len(cabecera)
    pesos = []
    for i in range(ncols):
        largo = max(len(fila[i]) if i < len(fila) else 1 for fila in filas)
        pesos.append(max(11, min(45, largo)))
    total = sum(pesos)
    anchos = [ANCHO_UTIL * p / total for p in pesos]

    datos = [[Paragraph(_inline(c), estilos["celda_cabecera"]) for c in cabecera]]
    for fila in cuerpo:
        fila = fila + [""] * (ncols - len(fila))
        datos.append([Paragraph(_inline(c), estilos["celda"]) for c in fila[:ncols]])

    tabla = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C2CC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tabla


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Title"], fontName="Helvetica-Bold",
                                 fontSize=17, leading=21, textColor=AZUL, spaceAfter=4),
        "subtitulo": ParagraphStyle("subtitulo", parent=base["Normal"], fontName="Helvetica",
                                    fontSize=9.5, leading=13, textColor=PIZARRA, alignment=TA_LEFT,
                                    spaceAfter=14),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold",
                             fontSize=14.5, leading=18, textColor=AZUL, spaceBefore=16, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                             fontSize=11.5, leading=15, textColor=AZUL, spaceBefore=12, spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName="Helvetica-BoldOblique",
                             fontSize=10.5, leading=14, textColor=AZUL, spaceBefore=9, spaceAfter=4),
        "cuerpo": ParagraphStyle("cuerpo", parent=base["BodyText"], fontName="Helvetica",
                                 fontSize=9.4, leading=13.2, textColor=colors.HexColor("#1F2933"),
                                 alignment=TA_JUSTIFY, spaceAfter=7),
        "vineta": ParagraphStyle("vineta", parent=base["BodyText"], fontName="Helvetica",
                                 fontSize=9.4, leading=13.2, textColor=colors.HexColor("#1F2933"),
                                 alignment=TA_LEFT, leftIndent=14, bulletIndent=4, spaceAfter=3),
        "codigo": ParagraphStyle("codigo", parent=base["Code"], fontName="Courier",
                                 fontSize=7.9, leading=10.5, textColor=colors.HexColor("#243B53"),
                                 backColor=colors.HexColor("#F1F4F7"), borderPadding=5,
                                 leftIndent=4, spaceBefore=4, spaceAfter=8),
        "celda_cabecera": ParagraphStyle("celda_cabecera", fontName="Helvetica-Bold", fontSize=8,
                                         leading=10, textColor=colors.white),
        "celda": ParagraphStyle("celda", fontName="Helvetica", fontSize=8, leading=10,
                                textColor=colors.HexColor("#1F2933")),
    }


def _bloques(texto, estilos):
    """Parser mínimo de Markdown: títulos, párrafos, viñetas, tablas y bloques de código."""
    lineas = texto.splitlines()
    flujo = []
    i = 0
    parrafo = []

    def cerrar_parrafo():
        if parrafo:
            flujo.append(Paragraph(_inline(" ".join(parrafo)), estilos["cuerpo"]))
            parrafo.clear()

    while i < len(lineas):
        linea = lineas[i].rstrip()
        if linea.startswith("```"):
            cerrar_parrafo()
            i += 1
            codigo = []
            while i < len(lineas) and not lineas[i].startswith("```"):
                codigo.append(lineas[i])
                i += 1
            flujo.append(Preformatted("\n".join(codigo), estilos["codigo"]))
            flujo.append(Spacer(1, 3))
            i += 1
            continue
        if linea.startswith("|"):
            cerrar_parrafo()
            filas = []
            while i < len(lineas) and lineas[i].startswith("|"):
                celdas = [c.strip() for c in lineas[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in celdas):
                    filas.append(celdas)
                i += 1
            if filas:
                flujo.append(_tabla(filas, estilos))
                flujo.append(Spacer(1, 8))
            continue
        if linea.startswith("- "):
            cerrar_parrafo()
            while i < len(lineas) and lineas[i].startswith("- "):
                flujo.append(Paragraph(_inline(lineas[i][2:].strip()), estilos["vineta"],
                                       bulletText="-"))
                i += 1
            flujo.append(Spacer(1, 3))
            continue
        if linea.startswith("### "):
            cerrar_parrafo()
            flujo.append(Paragraph(_inline(linea[4:]), estilos["h3"]))
        elif linea.startswith("## "):
            cerrar_parrafo()
            flujo.append(Paragraph(_inline(linea[3:]), estilos["h2"]))
        elif linea.startswith("# "):
            cerrar_parrafo()
            flujo.append(Paragraph(_inline(linea[2:]), estilos["h1"]))
        elif not linea.strip():
            cerrar_parrafo()
        else:
            parrafo.append(linea.strip())
        i += 1
    cerrar_parrafo()
    return flujo


def _decorar(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GRIS)
    canvas.setLineWidth(0.6)
    canvas.line(MARGEN, ALTO - 1.35 * cm, ANCHO - MARGEN, ALTO - 1.35 * cm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(PIZARRA)
    canvas.drawString(MARGEN, ALTO - 1.2 * cm,
                      "Laboratorio 11 · Observatorio de Turismo Sostenible · CC3066")
    canvas.drawRightString(ANCHO - MARGEN, ALTO - 1.2 * cm, "Secciones 5–8")
    canvas.line(MARGEN, 1.35 * cm, ANCHO - MARGEN, 1.35 * cm)
    canvas.drawString(MARGEN, 0.95 * cm, "Informe técnico — continuación de las secciones 1–4")
    canvas.drawRightString(ANCHO - MARGEN, 0.95 * cm, f"Página {doc.page}")
    canvas.restoreState()


def generar_secciones():
    estilos = _estilos()
    doc = BaseDocTemplate(str(NUEVO_PDF), pagesize=A4,
                          leftMargin=MARGEN, rightMargin=MARGEN,
                          topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                          title="Laboratorio 11 — Secciones 5 a 8",
                          author="Jose Ordoñez, Gadiel Ocaña, Adrián Gonzáles, José Antón",
                          subject="MLOps aplicado al Observatorio de Inteligencia Turística")
    marco = Frame(MARGEN, 1.8 * cm, ANCHO_UTIL, ALTO - 3.6 * cm, id="normal")
    doc.addPageTemplates([PageTemplate(id="pagina", frames=[marco], onPage=_decorar)])

    flujo = [
        Paragraph("Laboratorio 11 — MLOps aplicado al Observatorio de Turismo Sostenible", estilos["titulo"]),
        Paragraph("Secciones 5 a 8: regla de aceptación, tablero publicado, monitoreo y Docker. "
                  "Este bloque continúa el informe de las secciones 1–4 que se conserva en las páginas anteriores.", estilos["subtitulo"]),
    ]
    flujo += _bloques(FUENTE_MD.read_text(encoding="utf-8"), estilos)
    doc.build(flujo)
    return NUEVO_PDF


def unir():
    base = PdfReader(str(BASE_PDF))
    nuevo = PdfReader(str(NUEVO_PDF))
    writer = PdfWriter()
    for pagina in base.pages:
        writer.add_page(pagina)
    for pagina in nuevo.pages:
        writer.add_page(pagina)
    with open(SALIDA, "wb") as f:
        writer.write(f)
    return len(base.pages), len(nuevo.pages)


if __name__ == "__main__":
    generar_secciones()
    n_base, n_nuevo = unir()
    total = len(PdfReader(str(SALIDA)).pages)
    print(f"PDF generado: {SALIDA}")
    print(f"  base 1–4: {n_base} páginas")
    print(f"  secciones 5–8: {n_nuevo} páginas")
    print(f"  total: {total} páginas")
