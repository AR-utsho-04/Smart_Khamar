"""CSV and PDF report helpers (PDF text is English; reportlab cannot shape Bangla conjuncts)."""
import csv
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def to_csv(header, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens UTF-8 correctly


def to_pdf(title: str, blocks: list) -> bytes:
    """blocks: ('h', text) | ('p', text) | ('table', [header, *rows])"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm)
    st = getSampleStyleSheet()
    story = [Paragraph(title, st["Title"]), Spacer(1, 8)]
    for kind, val in blocks:
        if kind == "h":
            story += [Spacer(1, 8), Paragraph(val, st["Heading3"])]
        elif kind == "p":
            story.append(Paragraph(str(val).replace("&", "&amp;").replace("<", "&lt;"), st["BodyText"]))
        elif kind == "table" and val:
            data = [[Paragraph(str(c if c is not None else "-").replace("&", "&amp;").replace("<", "&lt;"), st["BodyText"]) for c in row] for row in val]
            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f3ec")),
                                   ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4bc")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(t)
    story.append(Spacer(1, 12))
    story.append(Paragraph("AI risk estimates support a veterinarian. They are not a diagnosis.", st["Italic"]))
    doc.build(story)
    return buf.getvalue()
