"""
URBANIA – Route: /api/geojson
Retorna el fixture enriquecido con scores como GeoJSON válido (RFC 7946).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from agents.demand_agent import compute_demand_score
from agents.risk_agent import compute_risk_score, classify_risk
from agents.business_agent import compute_opportunity_score, DECISION_MATRIX

router = APIRouter()

FIXTURE_PATH = Path(__file__).parent.parent / "data" / "mock_fixture.json"


def _load_geojson() -> dict:
    try:
        with open(FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Fixture GeoJSON no encontrado.")


@router.get("/enriched")
def enriched_geojson():
    """
    Retorna FeatureCollection con propiedades enriquecidas:
    demand_score, risk_score, opportunity_score, recomendacion, color_mapa.
    """
    fc = copy.deepcopy(_load_geojson())
    features = fc.get("features", [])

    for feature in features:
        props = feature["properties"]
        ds = compute_demand_score(feature)
        rs = compute_risk_score(feature)

        # Tier demand
        if ds >= 70:   d_tier = "ALTA"
        elif ds >= 45: d_tier = "MEDIA"
        else:          d_tier = "BAJA"

        r_tier = classify_risk(rs)
        opp    = compute_opportunity_score(ds, rs)

        decision = DECISION_MATRIX.get(
            (d_tier, r_tier),
            {"recomendacion": "EVALUAR", "color": "#6366f1"},
        )

        props.update({
            "demand_score":      ds,
            "risk_score":        rs,
            "opportunity_score": opp,
            "demand_tier":       d_tier,
            "risk_tier":         r_tier,
            "recomendacion":     decision["recomendacion"],
            "color_mapa":        decision["color"],
        })

    return JSONResponse(content=fc, media_type="application/geo+json")


@router.get("/raw")
def raw_geojson():
    """Retorna el GeoJSON original sin enriquecer."""
    return JSONResponse(
        content=_load_geojson(),
        media_type="application/geo+json",
    )
