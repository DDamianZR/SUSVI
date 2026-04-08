"""
URBANIA – Agente de Negocios
Combina demand_score y risk_score para producir una recomendación ejecutiva
y un score compuesto de oportunidad de negocio.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Matriz de decisión: (demand_tier, risk_tier) → recomendación
DECISION_MATRIX: dict[tuple[str, str], dict[str, Any]] = {
    ("ALTA",  "BAJO"):   {"recomendacion": "INVERTIR",  "color": "#10b981", "prioridad": 1},
    ("ALTA",  "MEDIO"):  {"recomendacion": "CAUTELA",   "color": "#f59e0b", "prioridad": 2},
    ("ALTA",  "ALTO"):   {"recomendacion": "CAUTELA",   "color": "#f59e0b", "prioridad": 3},
    ("MEDIA", "BAJO"):   {"recomendacion": "EVALUAR",   "color": "#6366f1", "prioridad": 4},
    ("MEDIA", "MEDIO"):  {"recomendacion": "EVALUAR",   "color": "#6366f1", "prioridad": 5},
    ("MEDIA", "ALTO"):   {"recomendacion": "DESCARTAR", "color": "#ef4444", "prioridad": 6},
    ("BAJA",  "BAJO"):   {"recomendacion": "EVALUAR",   "color": "#6366f1", "prioridad": 7},
    ("BAJA",  "MEDIO"):  {"recomendacion": "DESCARTAR", "color": "#ef4444", "prioridad": 8},
    ("BAJA",  "ALTO"):   {"recomendacion": "DESCARTAR", "color": "#ef4444", "prioridad": 9},
}


def compute_opportunity_score(demand_score: float, risk_score: float) -> float:
    """
    Score de oportunidad compuesto [0-100].
    Fórmula: 0.6 * demand_score + 0.4 * (100 - risk_score)
    """
    return round(0.6 * demand_score + 0.4 * (100.0 - risk_score), 2)


def classify_zones(
    demand_results: list[dict[str, Any]],
    risk_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Cruza resultados de demand_agent y risk_agent para producir
    la clasificación final de cada manzana.
    """
    risk_map = {r["id"]: r for r in risk_results}
    output = []

    for d in demand_results:
        manzana_id = d["id"]
        r = risk_map.get(manzana_id, {})

        demand_tier = d.get("demand_tier", "BAJA")
        risk_tier   = r.get("risk_tier",   "MEDIO")

        decision = DECISION_MATRIX.get(
            (demand_tier, risk_tier),
            {"recomendacion": "EVALUAR", "color": "#6366f1", "prioridad": 5},
        )

        opp = compute_opportunity_score(d["demand_score"], r.get("risk_score", 50))

        output.append({
            "id":                manzana_id,
            "nombre":            d.get("nombre"),
            "demand_score":      d["demand_score"],
            "risk_score":        r.get("risk_score", 0),
            "opportunity_score": opp,
            "demand_tier":       demand_tier,
            "risk_tier":         risk_tier,
            "recomendacion":     decision["recomendacion"],
            "color_mapa":        decision["color"],
            "prioridad":         decision["prioridad"],
        })

    output.sort(key=lambda x: x["opportunity_score"], reverse=True)
    logger.info("business_agent: clasificadas %d manzanas", len(output))
    return output


def generate_business_narrative(
    top_zones: list[dict[str, Any]],
    watsonx_client=None,
) -> str:
    """Genera resumen ejecutivo de oportunidades de negocio. Modo demo prefijado."""
    if watsonx_client is None:
        invertir = [z["nombre"] for z in top_zones if z["recomendacion"] == "INVERTIR"][:3]
        cautela  = [z["nombre"] for z in top_zones if z["recomendacion"] == "CAUTELA"][:2]
        return (
            f"Se identificaron {len(invertir)} zonas de inversión prioritaria: "
            f"{', '.join(invertir) if invertir else 'ninguna'}. "
            f"Las zonas {', '.join(cautela) if cautela else 'sin zonas'} requieren evaluación "
            "adicional de riesgo antes de comprometer capital. "
            "Se recomienda priorizar infraestructura logística en las zonas verdes."
        )

    prompt = _build_business_prompt(top_zones)
    response = watsonx_client.generate_text(prompt=prompt)
    return response.get("results", [{}])[0].get("generated_text", "")


def _build_business_prompt(zones: list[dict[str, Any]]) -> str:
    summary = json.dumps(zones[:6], ensure_ascii=False, indent=2)
    return (
        "Eres un consultor de expansión inmobiliaria y comercial. "
        "Con base en el análisis de demanda-riesgo siguiente, redacta un resumen "
        "ejecutivo (máximo 150 palabras) con recomendaciones claras de inversión:\n\n"
        f"{summary}\n\nResumen ejecutivo:"
    )
