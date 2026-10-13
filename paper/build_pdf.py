"""Gera o PDF de conferência das seções revisadas, a partir do Markdown."""

from html import escape
from io import BytesIO
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
from matplotlib import get_data_path
from matplotlib.mathtext import math_to_image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/TCC-secoes-revisadas.pdf"
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 54
WIDTH = PAGE_WIDTH - 2 * MARGIN


def inline(text):
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`(.+?)`", r"<font name='Body'>\1</font>", text)


def styles():
    fonts = Path(get_data_path()) / "fonts/ttf"
    for name, filename in [
        ("Body", "DejaVuSerif.ttf"), ("Body-Bold", "DejaVuSerif-Bold.ttf"),
        ("Body-Italic", "DejaVuSerif-Italic.ttf"),
        ("Body-BoldItalic", "DejaVuSerif-BoldItalic.ttf"),
    ]:
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold",
                                 italic="Body-Italic", boldItalic="Body-BoldItalic")
    sheet = getSampleStyleSheet()
    sheet.add(ParagraphStyle("Text", fontName="Body", fontSize=10.5, leading=15.5,
                             alignment=TA_JUSTIFY, spaceAfter=9))
    sheet.add(ParagraphStyle("TitleLocal", parent=sheet["Text"], fontName="Body-Bold",
                             fontSize=21, leading=28, alignment=0, spaceAfter=24))
    sheet.add(ParagraphStyle("H1", parent=sheet["Text"], fontName="Body-Bold",
                             fontSize=15, leading=21, spaceAfter=16, keepWithNext=True))
    sheet.add(ParagraphStyle("H2", parent=sheet["H1"], fontSize=12, leading=17,
                             spaceBefore=15, spaceAfter=10))
    sheet.add(ParagraphStyle("H3", parent=sheet["H2"], fontSize=10.7, leading=16,
                             spaceBefore=10, spaceAfter=8))
    sheet.add(ParagraphStyle("Cell", parent=sheet["Text"], fontSize=8.8,
                             leading=12.2, alignment=0, spaceAfter=0))
    sheet.add(ParagraphStyle("Small", parent=sheet["Text"], fontSize=8.7,
                             leading=12.4, alignment=0, spaceAfter=10))
    sheet.add(ParagraphStyle("EquationCaption", parent=sheet["Small"],
                             alignment=TA_CENTER, spaceBefore=6, spaceAfter=14))
    return sheet


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5df"))
    canvas.line(MARGIN, PAGE_HEIGHT - 35, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 35)
    canvas.setFont("Body", 8)
    canvas.setFillColor(colors.HexColor("#455463"))
    canvas.drawString(MARGIN, PAGE_HEIGHT - 27, "BrazilianInfoSim | Seções revisadas do TCC")
    canvas.drawString(MARGIN, 28, "Texto de substituição | PDF de conferência")
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 28, str(doc.page))
    canvas.restoreState()


def build():
    sheet = styles()
    lines = (ROOT / "paper/secoes-revisadas.md").read_text(encoding="utf-8").splitlines()
    story = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line:
            continue
        if line == "$$":
            equation = []
            while lines[index].strip() != "$$":
                equation.append(lines[index])
                index += 1
            index += 1
            stream = BytesIO()
            math_to_image("$" + " ".join(equation) + "$", stream, dpi=220,
                          format="png", color="#172330")
            stream.seek(0)
            formula = Image(stream)
            scale = min(WIDTH / formula.imageWidth, 72 / 150)
            formula.drawWidth = formula.imageWidth * scale
            formula.drawHeight = formula.imageHeight * scale
            formula.hAlign = "CENTER"
            block = [Spacer(1, 5), formula, Spacer(1, 6)]
            while index < len(lines) and not lines[index].strip():
                index += 1
            if index < len(lines) and lines[index].startswith("Equação "):
                block.append(Paragraph(inline(lines[index]), sheet["EquationCaption"]))
                index += 1
            story.append(KeepTogether(block))
            continue
        if line.startswith("|"):
            rows = [line]
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index].strip())
                index += 1
            rows = [row for row in rows if not re.fullmatch(r"[| :\-]+", row)]
            cells = [[Paragraph(inline(cell.strip()), sheet["Cell"])
                      for cell in row.strip("|").split("|")] for row in rows]
            cells[0] = [Paragraph("<b>" + inline(cell.strip()) + "</b>", sheet["Cell"])
                        for cell in rows[0].strip("|").split("|")]
            count = len(cells[0])
            ratios = {3: [0.23, 0.30, 0.47], 4: [0.27, 0.22, 0.27, 0.24],
                      5: [0.30, 0.175, 0.175, 0.175, 0.175]}[count]
            if "Situação" in rows[0]:
                ratios = [0.24, 0.18, 0.58]
            table = Table(cells, colWidths=[WIDTH * ratio for ratio in ratios],
                          repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5edf3")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#8091a1")),
                ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#8091a1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            story.extend([table, Spacer(1, 8)])
            continue
        if line.startswith("# "):
            if story:
                story.append(PageBreak())
            style = "TitleLocal" if not story else "H1"
            story.append(Paragraph(inline(line[2:]), sheet[style]))
            continue
        if line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), sheet["H2"]))
            continue
        if line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), sheet["H3"]))
            continue
        if line.startswith("Equação "):
            style = "EquationCaption"
        elif line.startswith("Fonte:"):
            style = "Small"
        else:
            style = "Text"
        text = line[2:] if line.startswith("- ") else line
        paragraph = Paragraph(inline(text), sheet[style],
                              bulletText="•" if line.startswith("- ") else None)
        if line.startswith("**Tabela "):
            paragraph.keepWithNext = True
        if line.endswith(":") and index < len(lines):
            following = next((item.strip() for item in lines[index:] if item.strip()), "")
            if following == "$$":
                paragraph.keepWithNext = True
        story.append(paragraph)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=MARGIN,
                                rightMargin=MARGIN, topMargin=55, bottomMargin=48,
                                title="BrazilianInfoSim: seções revisadas do TCC",
                                author="Revisão do projeto BrazilianInfoSim")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    build()
