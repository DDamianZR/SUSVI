"""
URBANIA – Agente de Demanda
Analiza densidad poblacional, actividad económica DENUE y accesibilidad GTFS
para calcular el score de demanda de cada manzana.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Pesos del score de demanda ────────────────────────────────────────────────
WEIGHTS = {
    "densidad_poblacional":     0.30,
    "actividad_economica_denue": 0.35,
    "luminosidad_viirs":         0.20,
    "acceso_gtfs":               0.15,
}

# Rangos normalizados (min, max) por variable
RANGES = {
    "densidad_poblacional":      (500,  25_000),
    "actividad_economica_denue": (0,    400),
    "luminosidad_viirs":         (0,    255),
    "acceso_gtfs":               (0,    1),
}


def _normalize(value: float, vmin: float, vmax: float) -> float:
    """Normaliza un valor al rango [0, 1]."""
    if vmax == vmin:
        return 0.0
    return max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))


def compute_demand_score(feature: dict[str, Any]) -> float:
    """
    Calcula el score de demanda [0-100] para una Feature GeoJSON.

    Args:
        feature: Un Feature GeoJSON con las propiedades del fixture.

    Returns:
        Score de demanda normalizado entre 0 y 100.
    """
    props = feature.get("properties", {})
    score = 0.0

    for field, weight in WEIGHTS.items():
        raw = props.get(field, 0)
        # Booleano → numérico
        if isinstance(raw, bool):
            raw = 1.0 if raw else 0.0
        vmin, vmax = RANGES[field]
        norm = _normalize(float(raw), vmin, vmax)
        score += norm * weight

    return round(score * 100, 2)


def analyze_demand(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Enriquece una lista de Features con el score de demanda y su clasificación.

    Returns:
        Lista de dicts con id, nombre, demand_score y demand_tier.
    """
    results = []
    for f in features:
        props = f.get("properties", {})
        ds = compute_demand_score(f)

        if ds >= 70:
            tier = "ALTA"
        elif ds >= 45:
            tier = "MEDIA"
        else:
            tier = "BAJA"

        results.append({
            "id":           props.get("id"),
            "nombre":       props.get("nombre"),
            "demand_score": ds,
            "demand_tier":  tier,
        })

    results.sort(key=lambda x: x["demand_score"], reverse=True)
    logger.info("demand_agent: analizadas %d manzanas", len(results))
    return results


# ── Stub para integración Watsonx (activar en producción) ────────────────────

def generate_demand_narrative(
    top_features: list[dict[str, Any]],
    watsonx_client=None,
) -> str:
    """
    Genera un análisis narrativo de demanda usando IBM Watsonx AI (Granite 13B).
    En modo demo retorna texto preconfigurado.
    """
    if watsonx_client is None:
        # Modo demo – fixture mock
        names = [f["nombre"] for f in top_features[:3]]
        return (
            f"Las manzanas con mayor potencial de demanda identificadas son: "
            f"{', '.join(names)}. Presentan alta densidad poblacional, "
            "actividad económica DENUE robusta y buena conectividad GTFS, "
            "lo que las posiciona como zonas prioritarias para intervención comercial."
        )

    # Producción: llamada real al modelo Granite 13B
    prompt = _build_demand_prompt(top_features)
    response = watsonx_client.generate_text(prompt=prompt)
    return response.get("results", [{}])[0].get("generated_text", "")


def _build_demand_prompt(features: list[dict[str, Any]]) -> str:
    summary = json.dumps(features[:5], ensure_ascii=False, indent=2)
    return (
        "Eres un analista de inteligencia territorial. "
        "Analiza las siguientes manzanas según su score de demanda y redacta "
        "un párrafo ejecutivo conciso (máximo 120 palabras) destacando las "
        "oportunidades de inversión:\n\n"
        f"{summary}\n\nAnálisis:"
    )
