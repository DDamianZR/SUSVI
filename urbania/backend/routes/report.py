"""
URBANIA – Route: /api/report
Genera un PDF ejecutivo usando ReportLab con los resultados del análisis.
"""
from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

from agents.demand_agent import analyze_demand, generate_demand_narrative
from agents.risk_agent import analyze_risk, generate_risk_narrative
from agents.business_agent import classify_zones, generate_business_narrative

router = APIRouter()

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "mock_fixture.json"

# ── Color palette URBANIA ────────────────────────────────────────────────────
C_DARK   = colors.HexColor("#0a0e1a")
C_ACCENT = colors.HexColor("#6366f1")
C_GREEN  = colors.HexColor("#10b981")
C_YELLOW = colors.HexColor("#f59e0b")
C_RED    = colors.HexColor("#ef4444")
C_LIGHT  = colors.HexColor("#f1f5f9")
C_MUTED  = colors.HexColor("#64748b")


def _recomendacion_color(rec: str) -> colors.Color:
    mapping = {
        "INVERTIR":  C_GREEN,
        "CAUTELA":   C_YELLOW,
        "EVALUAR":   C_ACCENT,
        "DESCARTAR": C_RED,
    }
    return mapping.get(rec, C_MUTED)


@router.get("/pdf")
def generate_pdf_report():
    """Genera y descarga el reporte ejecutivo en PDF."""

    with open(FIXTURE_PATH, encoding="utf-8") as f:
        fc = json.load(f)
    features = fc.get("features", [])

    demand_r   = analyze_demand(features)
    risk_r     = analyze_risk(features)
    business_r = classify_zones(demand_r, risk_r)

    top_demand = [d for d in demand_r  if d["demand_tier"] == "ALTA"][:5]
    high_risk  = [r for r in risk_r    if r["risk_tier"]  == "ALTO"][:5]

    narrative_demand   = generate_demand_narrative(top_demand)
    narrative_risk     = generate_risk_narrative(high_risk)
    narrative_business = generate_business_narrative(business_r[:6])

    # ── Build PDF in-memory ──────────────────────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "UrbaniaTitle",
        parent=styles["Title"],
        textColor=C_ACCENT,
        fontSize=22,
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "UrbaniaHeading",
        parent=styles["Heading2"],
        textColor=C_DARK,
        fontSize=13,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "UrbaniaBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
    )

    story = []

    # ── Header ───────────────────────────────────────────────────────────────
    story.append(Paragraph("URBANIA", title_style))
    story.append(Paragraph("Reporte Ejecutivo de Inteligencia Territorial", styles["Heading2"]))
    story.append(Paragraph(f"Zona Piloto CDMX  ·  {date.today().isoformat()}", body_style))
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceAfter=10))

    # ── Resumen ejecutivo ────────────────────────────────────────────────────
    story.append(Paragraph("Resumen Ejecutivo", heading_style))
    story.append(Paragraph(narrative_business, body_style))
    story.append(Spacer(1, 10))

    # ── Análisis de demanda ──────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=C_MUTED, spaceAfter=6))
    story.append(Paragraph("Análisis de Demanda", heading_style))
    story.append(Paragraph(narrative_demand, body_style))
    story.append(Spacer(1, 8))

    demand_table_data = [["#", "Manzana", "Score", "Nivel"]] + [
        [i + 1, d["nombre"], f"{d['demand_score']:.1f}", d["demand_tier"]]
        for i, d in enumerate(demand_r[:10])
    ]
    demand_table = Table(demand_table_data, colWidths=[0.4*inch, 2.8*inch, 1*inch, 1*inch])
    demand_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_ACCENT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ALIGN",      (2, 0), (-1, -1), "CENTER"),
    ]))
    story.append(demand_table)
    story.append(Spacer(1, 12))

    # ── Análisis de riesgo ───────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=C_MUTED, spaceAfter=6))
    story.append(Paragraph("Análisis de Riesgo", heading_style))
    story.append(Paragraph(narrative_risk, body_style))
    story.append(Spacer(1, 8))

    risk_table_data = [["#", "Manzana", "Score", "Nivel", "Delito Principal"]] + [
        [i+1, r["nombre"], f"{r['risk_score']:.1f}", r["risk_tier"], r["tipo_delito"]]
        for i, r in enumerate(risk_r[:10])
    ]
    risk_table = Table(risk_table_data, colWidths=[0.4*inch, 2*inch, 0.8*inch, 0.8*inch, 2.2*inch])
    risk_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_RED),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff7f7")]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ALIGN",      (2, 0), (-1, -1), "CENTER"),
    ]))
    story.append(risk_table)
    story.append(Spacer(1, 12))

    # ── Clasificación de zonas ───────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=C_MUTED, spaceAfter=6))
    story.append(Paragraph("Clasificación de Oportunidades", heading_style))
    biz_table_data = [["#", "Manzana", "Oportunidad", "Demanda", "Riesgo", "Recomendación"]] + [
        [
            i+1, b["nombre"],
            f"{b['opportunity_score']:.1f}",
            b["demand_tier"], b["risk_tier"],
            b["recomendacion"],
        ]
        for i, b in enumerate(business_r[:10])
    ]
    biz_table = Table(biz_table_data, colWidths=[0.4*inch, 1.8*inch, 1*inch, 0.9*inch, 0.8*inch, 1.3*inch])
    biz_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ALIGN",      (2, 0), (-1, -1), "CENTER"),
    ]))
    story.append(biz_table)

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=C_MUTED))
    story.append(Paragraph(
        "Generado por URBANIA · Plataforma SaaS B2B de Inteligencia Territorial · Datos: Zona Piloto CDMX (Demo)",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, textColor=C_MUTED, alignment=1),
    ))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=urbania_reporte.pdf"},
    )
