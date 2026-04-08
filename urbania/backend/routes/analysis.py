"""
URBANIA – Route: /api/analysis
Orquesta los tres agentes (Demanda, Riesgo, Negocios) sobre el fixture mock.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.demand_agent import analyze_demand, generate_demand_narrative
from agents.risk_agent import analyze_risk, generate_risk_narrative
from agents.business_agent import classify_zones, generate_business_narrative

router = APIRouter()

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "mock_fixture.json"


def _load_features() -> list[dict]:
    try:
        with open(FIXTURE_PATH, encoding="utf-8") as f:
            fc = json.load(f)
        return fc.get("features", [])
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Fixture no encontrado.")


class AnalysisResponse(BaseModel):
    total_manzanas: int
    demand: list[dict]
    risk: list[dict]
    business: list[dict]
    narrative_demand: str
    narrative_risk: str
    narrative_business: str


@router.get("/full", response_model=AnalysisResponse)
def full_analysis():
    """Ejecuta los tres agentes y retorna análisis completo."""
    features = _load_features()

    demand_results   = analyze_demand(features)
    risk_results     = analyze_risk(features)
    business_results = classify_zones(demand_results, risk_results)

    top_demand   = [d for d in demand_results   if d["demand_tier"] == "ALTA"][:5]
    high_risk    = [r for r in risk_results     if r["risk_tier"]   == "ALTO"][:5]

    return AnalysisResponse(
        total_manzanas=len(features),
        demand=demand_results,
        risk=risk_results,
        business=business_results,
        narrative_demand=generate_demand_narrative(top_demand),
        narrative_risk=generate_risk_narrative(high_risk),
        narrative_business=generate_business_narrative(business_results[:6]),
    )


@router.get("/demand")
def demand_only():
    """Solo scores de demanda."""
    return analyze_demand(_load_features())


@router.get("/risk")
def risk_only():
    """Solo scores de riesgo."""
    return analyze_risk(_load_features())


@router.get("/business")
def business_only():
    """Solo clasificación de negocio (sin narrativas)."""
    features = _load_features()
    return classify_zones(analyze_demand(features), analyze_risk(features))
