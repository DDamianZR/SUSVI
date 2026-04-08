"""
URBANIA – Agente de Riesgo
Evalúa incidencia delictiva SNSP, iluminación pública y accesibilidad logística
para calcular el score de riesgo de cada manzana.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Pesos del score de riesgo ─────────────────────────────────────────────────
WEIGHTS = {
    "incidencia_delictiva_snsp": 0.45,
    "iluminacion_publica":       0.30,   # inverso: <iluminación → +riesgo
    "luminosidad_viirs":         0.25,   # inverso: <luz → +riesgo
}

RANGES = {
    "incidencia_delictiva_snsp": (0,   500),
    "iluminacion_publica":       (0,   100),
    "luminosidad_viirs":         (0,   255),
}


def _normalize(value: float, vmin: float, vmax: float) -> float:
    if vmax == vmin:
        return 0.0
    return max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))


def compute_risk_score(feature: dict[str, Any]) -> float:
    """
    Calcula el score de riesgo [0-100] para una Feature GeoJSON.
    Un score alto indica MAYOR riesgo.
    """
    props = feature.get("properties", {})

    # Incidencia delictiva: a mayor valor → mayor riesgo (directa)
    delitos = float(props.get("incidencia_delictiva_snsp", 0))
    norm_delitos = _normalize(delitos, *RANGES["incidencia_delictiva_snsp"])

    # Iluminación pública: a menor valor → mayor riesgo (inversa)
    ilum = float(props.get("iluminacion_publica", 50))
    norm_ilum = 1.0 - _normalize(ilum, *RANGES["iluminacion_publica"])

    # Luminosidad VIIRS: a menor valor → mayor riesgo (inversa)
    viirs = float(props.get("luminosidad_viirs", 128))
    norm_viirs = 1.0 - _normalize(viirs, *RANGES["luminosidad_viirs"])

    score = (
        norm_delitos * WEIGHTS["incidencia_delictiva_snsp"]
        + norm_ilum  * WEIGHTS["iluminacion_publica"]
        + norm_viirs * WEIGHTS["luminosidad_viirs"]
    )
    return round(score * 100, 2)


def classify_risk(risk_score: float) -> str:
    if risk_score >= 65:
        return "ALTO"
    elif risk_score >= 35:
        return "MEDIO"
    return "BAJO"


def analyze_risk(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Enriquece una lista de Features GeoJSON con score de riesgo y clasificación.
    """
    results = []
    for f in features:
        props = f.get("properties", {})
        rs = compute_risk_score(f)
        results.append({
            "id":              props.get("id"),
            "nombre":          props.get("nombre"),
            "risk_score":      rs,
            "risk_tier":       classify_risk(rs),
            "tipo_delito":     props.get("tipo_delito_predominante", "N/D"),
            "delitos_anuales": props.get("incidencia_delictiva_snsp", 0),
        })

    results.sort(key=lambda x: x["risk_score"], reverse=True)
    logger.info("risk_agent: analizadas %d manzanas", len(results))
    return results


def generate_risk_narrative(
    high_risk_features: list[dict[str, Any]],
    watsonx_client=None,
) -> str:
    """Genera análisis narrativo de riesgo. Modo demo retorna texto prefijado."""
    if watsonx_client is None:
        names = [f["nombre"] for f in high_risk_features[:3]]
        return (
            f"Las manzanas {', '.join(names)} presentan niveles de riesgo elevados "
            "principalmente por alta incidencia delictiva y déficit de iluminación pública. "
            "Se recomienda evaluar medidas de mitigación antes de cualquier inversión."
        )

    prompt = _build_risk_prompt(high_risk_features)
    response = watsonx_client.generate_text(prompt=prompt)
    return response.get("results", [{}])[0].get("generated_text", "")


def _build_risk_prompt(features: list[dict[str, Any]]) -> str:
    summary = json.dumps(features[:5], ensure_ascii=False, indent=2)
    return (
        "Eres un analista de seguridad territorial. "
        "Redacta un párrafo ejecutivo (máximo 120 palabras) sobre los factores de riesgo "
        "de las siguientes manzanas urbanas:\n\n"
        f"{summary}\n\nAnálisis de riesgo:"
    )
