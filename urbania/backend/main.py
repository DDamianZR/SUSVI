"""
URBANIA - API REST (FastAPI)
============================

Punto de entrada principal para URBANIA. Orquesta la ejecucion en paralelo de
agentes de inteligencia territorial (Demanda, Riesgo, Negocios) y expone
los endpoints requeridos por el frontend (React/Leaflet).

Cambios respecto al prototipo original:
- Se elimina IBM Cloud Object Storage (sin tier gratuito).
  El almacenamiento usa disco local (tmp/) para PDFs y cache en memoria.
- Se agrega startup event que pre-genera demo_result.json si no existe.
- Se agrega endpoint GET /api/v1/export/raw-data/{analysis_id} para
  exponer todos los datos crudos que seran interpretados en capa posterior.
- health() incluye campo mock_mode para que el frontend lo muestre.
"""
import asyncio
import copy
import json
import logging
import os
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

# ── Importaciones Internas ─────────────────────────────────────────────────────
from data.ingest import flag_production_sources, load_mock_fixture, run_ingestion
from agents.demand_agent import DemandAgent
from agents.risk_agent import RiskAgent
from agents.business_agent import BusinessAgent
from utils.pdf_generator import URBANIAReportGenerator

# ── 1. Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("urbania.api")

# ── 2. App FastAPI ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="URBANIA API REST",
    description="Motor B2B de inteligencia territorial con IBM Watsonx AI (modo fallback algoritmico para demo).",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── 3. CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",   # Vite preview
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        "%s %s → %s (%.3fs)",
        request.method, request.url.path,
        response.status_code, process_time
    )
    return response

# ── 4. Cache en memoria (sin IBM COS) ─────────────────────────────────────────
MAX_HISTORY = 20
_analysis_history: OrderedDict[str, dict] = OrderedDict()

def _demo_result_path() -> str:
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    return os.path.join(data_dir, "demo_result.json")

def _tmp_dir() -> str:
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
    os.makedirs(d, exist_ok=True)
    return d

# ── 5. Startup: generar demo_result.json si no existe ─────────────────────────
@app.on_event("startup")
async def _bootstrap_demo():
    demo_path = _demo_result_path()
    if os.path.exists(demo_path):
        logger.info("demo_result.json ya existe. Cargando en cache...")
        try:
            with open(demo_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            _analysis_history[cached.get("analysis_id", "demo")] = cached
        except Exception as e:
            logger.warning("Error cargando demo_result.json existente: %s", e)
        return

    logger.info("demo_result.json no existe. Generando demo seed con parámetros AXTEL...")
    try:
        # Parámetros del caso real: AXTEL · 12 antenas · $2M cada una · 8 años
        demo_params = {
            "sector": "telecomunicaciones",
            "params": {
                "ticket_inversion_mxn": 2_000_000.0,
                "vida_util_anios": 8,
                "tasa_descuento": 0.12,
                "n_unidades_objetivo": 12,
            }
        }

        analysis_id = "demo-seed-axtel-cdmx"
        features_norm = await asyncio.to_thread(run_ingestion, {}, demo_params["sector"])

        demand_agent = DemandAgent(sector=demo_params["sector"], use_fallback_only=True)
        risk_agent = RiskAgent(use_fallback_only=True)
        business_agent = BusinessAgent(use_fallback_only=True)

        demand_scores, risk_scores = await asyncio.gather(
            asyncio.to_thread(demand_agent.score, features_norm, demo_params["sector"]),
            asyncio.to_thread(risk_agent.score, features_norm)
        )

        b_params = {**demo_params["params"], "sector": demo_params["sector"]}
        business_results = await asyncio.to_thread(
            business_agent.generate_scenarios,
            demand_scores, risk_scores, b_params
        )

        data_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(data_dir, "data")
        original_geojson = await asyncio.to_thread(
            load_mock_fixture, os.path.join(data_dir, "mock_fixture.json")
        )

        demand_geojson = await asyncio.to_thread(
            demand_agent.to_geojson, demand_scores, original_geojson
        )
        risk_geojson = await asyncio.to_thread(
            risk_agent.generate_risk_geojson, risk_scores, original_geojson
        )

        viables = [
            {
                "id": feat["id"],
                "score_viabilidad": feat["score_viabilidad"],
                "clasificacion": feat["categoria_viabilidad"]
            }
            for feat in business_results.get("features_score_viabilidad", [])
        ]

        result = {
            "analysis_id": analysis_id,
            "demand_geojson": demand_geojson,
            "risk_geojson": risk_geojson,
            "viability_scores": viables,
            "scenarios": business_results.get("escenarios_algoritmicos", []),
            "executive_report": business_results.get("reporte_ejecutivo", {}),
            "metadata": {
                "sector": demo_params["sector"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "n_manzanas_analizadas": len(features_norm),
                "prod_mode": False,
                "zone_filtered": False,
                "demo_context": "Caso AXTEL: 12 antenas 4G/5G · CDMX · $24M MXN",
                "parametros": demo_params["params"]
            }
        }

        # Guardar en disco (sin IBM COS)
        with open(demo_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        _analysis_history[analysis_id] = result
        logger.info("✅ demo_result.json generado exitosamente con %d manzanas.", len(features_norm))

    except Exception as e:
        logger.error("Error generando demo seed: %s", e, exc_info=True)


# ── 6. Modelos Pydantic ────────────────────────────────────────────────────────

class BusinessParams(BaseModel):
    ticket_inversion_mxn: float = Field(..., gt=0)
    vida_util_anios: int = Field(..., gt=0)
    tasa_descuento: float = Field(..., gt=0, lt=1)
    n_unidades_objetivo: int = Field(..., gt=0)

class AnalyzeRequest(BaseModel):
    zone_polygon: Optional[Dict[str, Any]] = None
    sector: str = Field(..., pattern="^(telecomunicaciones|seguridad|inmobiliario)$")
    params: BusinessParams

class ExportGeojsonRequest(BaseModel):
    analysis_id: str

class ExportReportRequest(BaseModel):
    analysis_id: str
    format: str = Field(default="json", pattern="^(json|pdf_ready|pdf)$")


# ── 7. Endpoints ───────────────────────────────────────────────────────────────

@app.post("/api/v1/analyze", summary="Ejecutar Análisis de Inteligencia Territorial")
async def analyze_zone(req: AnalyzeRequest):
    """
    Orquesta Ingesta → Agente Demanda → Agente Riesgo → Agente Negocios en paralelo.

    En modo demo (URBANIA_PROD_MODE=0) usa el fixture local.
    No requiere IBM Cloud Object Storage; el storage es en-memoria + disco local.
    """
    analysis_id = str(uuid.uuid4())
    logger.info("ANALYZE start | ID=%s | sector=%s", analysis_id, req.sector)

    try:
        zone_arg = req.zone_polygon or {}
        features_norm = await asyncio.to_thread(run_ingestion, zone_arg, req.sector)

        if not features_norm:
            raise HTTPException(
                status_code=400,
                detail="El polígono no intersecta con ninguna manzana disponible."
            )

        is_prod_mode = flag_production_sources()

        demand_agent = DemandAgent(sector=req.sector, use_fallback_only=not is_prod_mode)
        risk_agent = RiskAgent(use_fallback_only=not is_prod_mode)
        business_agent = BusinessAgent(use_fallback_only=not is_prod_mode)

        demand_scores, risk_scores = await asyncio.gather(
            asyncio.to_thread(demand_agent.score, features_norm, req.sector),
            asyncio.to_thread(risk_agent.score, features_norm)
        )

        b_params = req.params.model_dump()
        b_params["sector"] = req.sector

        business_results = await asyncio.to_thread(
            business_agent.generate_scenarios, demand_scores, risk_scores, b_params
        )

        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        original_geojson = await asyncio.to_thread(
            load_mock_fixture, os.path.join(data_dir, "mock_fixture.json")
        )

        demand_geojson = await asyncio.to_thread(
            demand_agent.to_geojson, demand_scores, original_geojson
        )
        risk_geojson = await asyncio.to_thread(
            risk_agent.generate_risk_geojson, risk_scores, original_geojson
        )

        viables = [
            {
                "id": feat["id"],
                "score_viabilidad": feat["score_viabilidad"],
                "clasificacion": feat["categoria_viabilidad"]
            }
            for feat in business_results.get("features_score_viabilidad", [])
        ]

        response_data = {
            "analysis_id": analysis_id,
            "demand_geojson": demand_geojson,
            "risk_geojson": risk_geojson,
            "viability_scores": viables,
            "scenarios": business_results.get("escenarios_algoritmicos", []),
            "executive_report": business_results.get("reporte_ejecutivo", {}),
            "metadata": {
                "sector": req.sector,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "n_manzanas_analizadas": len(features_norm),
                "prod_mode": is_prod_mode,
                "zone_filtered": bool(zone_arg),
                "parametros": req.params.model_dump()
            }
        }

        if len(_analysis_history) >= MAX_HISTORY:
            _analysis_history.popitem(last=False)
        _analysis_history[analysis_id] = response_data

        logger.info("ANALYZE done | ID=%s | manzanas=%d", analysis_id, len(features_norm))
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en analyze_zone: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/api/v1/mock-zone", summary="GeoJSON fixture crudo (mapa inicial)")
def get_mock_zone():
    """Retorna el FeatureCollection CDMX base para poblar el mapa antes del análisis."""
    try:
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        return load_mock_fixture(os.path.join(data_dir, "mock_fixture.json"))
    except Exception as e:
        logger.error("Error leyendo mock_fixture: %s", e)
        raise HTTPException(status_code=500, detail="Fixture no disponible.")


@app.get("/api/v1/demo-result", summary="Resultado pre-calculado del demo seed")
def get_demo_result():
    """Retorna el resultado pre-calculado (generado en startup) para demo instantáneo."""
    # Primero buscar en cache memoria
    if "demo-seed-axtel-cdmx" in _analysis_history:
        return _analysis_history["demo-seed-axtel-cdmx"]

    # Luego buscar en disco
    demo_path = _demo_result_path()
    if not os.path.exists(demo_path):
        raise HTTPException(
            status_code=404,
            detail="Demo seed aún no generado. El servidor lo genera en startup automáticamente."
        )
    try:
        with open(demo_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _analysis_history[data.get("analysis_id", "demo")] = data
        return data
    except Exception as e:
        logger.error("Error leyendo demo_result.json: %s", e)
        raise HTTPException(status_code=500, detail="Error leyendo cache local.")


@app.get("/api/v1/health", summary="Health check y estado del sistema")
def health_check():
    """Comprueba el entorno y retorna estado del sistema."""
    prod_mode = flag_production_sources()
    wx_url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

    wx_ok = False
    if prod_mode:
        import urllib.request
        try:
            code = urllib.request.urlopen(wx_url, timeout=3.0).getcode()
            wx_ok = code is not None and code < 500
        except Exception as e:
            logger.warning("Watsonx ping fallido: %s", e)
    else:
        wx_ok = True  # fallback algorítmico siempre disponible

    return {
        "status": "ok",
        "mock_mode": not prod_mode,          # <-- Campo que usa el frontend
        "watsonx_prod_enabled": prod_mode,
        "watsonx_network_ok": wx_ok,
        "storage": "local_disk",             # Sin IBM COS
        "demo_seed_ready": os.path.exists(_demo_result_path()),
        "analysis_cached": len(_analysis_history),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/v1/export/geojson", summary="Exportar GeoJSON consolidado")
async def export_geojson(req: ExportGeojsonRequest):
    """Exporta GeoJSON con Demanda + Riesgo + Viabilidad fusionados."""
    data = _analysis_history.get(req.analysis_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="Analysis ID no encontrado en la cache. El análisis expiró o no existe."
        )

    export_json = copy.deepcopy(data["demand_geojson"])
    risk_map = {f["id"]: f for f in data["risk_geojson"].get("features", []) if "id" in f}
    viability_map = {f["id"]: f for f in data["viability_scores"]}

    for feat in export_json.get("features", []):
        props = feat.setdefault("properties", {})
        fid = props.get("id") or feat.get("id")

        r_node = risk_map.get(fid)
        if r_node:
            r_props = r_node.get("properties", {})
            props["score_riesgo"]               = r_props.get("score_riesgo")
            props["clasificacion_riesgo"]       = r_props.get("clasificacion")
            props["color_leaflet_riesgo"]       = r_props.get("color_leaflet")
            props["factores_riesgo"]            = r_props.get("factores_riesgo")
            props["recomendaciones_mitigacion"] = r_props.get("recomendaciones_mitigacion")
            props["razon_descarte"]             = r_props.get("razon_descarte")

        v_node = viability_map.get(fid)
        if v_node:
            props["score_viabilidad"]       = v_node.get("score_viabilidad")
            props["clasificacion_negocios"] = v_node.get("clasificacion")

    return JSONResponse(
        content=export_json,
        headers={"Content-Disposition": f'attachment; filename="urbania_{req.analysis_id[:8]}.geojson"'}
    )


@app.get("/api/v1/export/raw-data/{analysis_id}", summary="Exportar datos crudos para interpretación")
async def export_raw_data(analysis_id: str):
    """
    Exporta TODOS los datos en su forma más granular para interpretación posterior.

    Esto incluye:
    - Scores por manzana (demanda, riesgo, viabilidad)
    - Factores de riesgo detallados por zona
    - Justificaciones top-3 por zona
    - Datos normalizados del fixture
    - Escenarios financieros completos
    - Resumen ejecutivo raw

    Estos datos NO son la interpretación final. Son los datos brutos para
    que la capa de interpretación los procese y presente al usuario final.
    """
    data = _analysis_history.get(analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis ID no encontrado.")

    # Construir estructura completa de datos crudos
    raw_export = {
        "analysis_id": analysis_id,
        "metadata": data["metadata"],
        "raw_scores": {
            "viability_scores": data["viability_scores"],
            "demand_features_count": len(data["demand_geojson"].get("features", [])),
            "risk_features_count": len(data["risk_geojson"].get("features", [])),
        },
        "demand_geojson_enriched": _extract_demand_properties(data["demand_geojson"]),
        "risk_geojson_enriched": _extract_risk_properties(data["risk_geojson"]),
        "scenarios_raw": data["scenarios"],
        "executive_report_raw": data["executive_report"],
        "clasifications_summary": _summarize_classifications(data["viability_scores"]),
    }

    return JSONResponse(content=raw_export)


def _extract_demand_properties(demand_geojson: dict) -> list:
    """Extrae propiedades de demanda por manzana para raw export."""
    result = []
    for feat in demand_geojson.get("features", []):
        props = feat.get("properties", {})
        result.append({
            "id": props.get("id"),
            "nombre": props.get("nombre"),
            "score_demanda": props.get("score_demanda"),
            "demand_tier": props.get("demand_tier"),
            "justificacion_top3": props.get("justificacion_top3", []),
            "score_source": props.get("score_source"),
            "lat": props.get("lat"),
            "lng": props.get("lng"),
            # Datos originales del fixture para interpretación
            "densidad_poblacional": props.get("densidad_poblacional"),
            "actividad_economica_denue": props.get("actividad_economica_denue"),
            "luminosidad_viirs": props.get("luminosidad_viirs"),
            "acceso_gtfs": props.get("acceso_gtfs"),
        })
    return result


def _extract_risk_properties(risk_geojson: dict) -> list:
    """Extrae propiedades de riesgo por manzana para raw export."""
    result = []
    for feat in risk_geojson.get("features", []):
        props = feat.get("properties", {})
        result.append({
            "id": props.get("id"),
            "nombre": props.get("nombre"),
            "score_riesgo": props.get("score_riesgo"),
            "clasificacion": props.get("clasificacion"),
            "factores_riesgo": props.get("factores_riesgo", []),
            "recomendaciones_mitigacion": props.get("recomendaciones_mitigacion", []),
            "razon_descarte": props.get("razon_descarte"),
            "color_leaflet": props.get("color_leaflet"),
            # Datos de incidencia originales
            "incidencia_delictiva_snsp": props.get("incidencia_delictiva_snsp"),
            "tipo_delito_predominante": props.get("tipo_delito_predominante"),
            "iluminacion_publica": props.get("iluminacion_publica"),
            "accesibilidad_logistica": props.get("accesibilidad_logistica"),
        })
    return result


def _summarize_classifications(viability_scores: list) -> dict:
    """Resume la distribución de clasificaciones."""
    counts = {"Alta viabilidad": 0, "Viabilidad media": 0, "Descarte": 0}
    for v in viability_scores:
        cat = v.get("clasificacion", "Descarte")
        counts[cat] = counts.get(cat, 0) + 1
    total = len(viability_scores)
    return {
        "total_manzanas": total,
        "zonas_verdes": counts["Alta viabilidad"],
        "zonas_cautela": counts["Viabilidad media"],
        "zonas_descarte": counts["Descarte"],
        "pct_verde": round(counts["Alta viabilidad"] / max(total, 1) * 100, 1),
        "pct_cautela": round(counts["Viabilidad media"] / max(total, 1) * 100, 1),
        "pct_descarte": round(counts["Descarte"] / max(total, 1) * 100, 1),
    }


@app.post("/api/v1/export/report", summary="Exportar reporte ejecutivo")
async def export_report(req: ExportReportRequest):
    """
    Exporta el reporte ejecutivo en formato JSON o PDF.
    El PDF se genera localmente (sin IBM Cloud Object Storage).
    """
    data = _analysis_history.get(req.analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis ID no encontrado.")

    if req.format == "pdf_ready":
        dummy_agent = BusinessAgent(use_fallback_only=True)
        pdf_dict = dummy_agent.to_pdf_ready_dict({"reporte_ejecutivo": data["executive_report"]})
        pdf_dict.update({"analysis_id": data["analysis_id"], "metadata": data["metadata"]})
        return pdf_dict

    if req.format == "pdf":
        dummy_agent = BusinessAgent(use_fallback_only=True)
        pdf_dict = dummy_agent.to_pdf_ready_dict({"reporte_ejecutivo": data["executive_report"]})
        pdf_dict.update({"analysis_id": data["analysis_id"], "metadata": data["metadata"]})

        vs = data.get("viability_scores", [])
        pdf_dict["kpis"] = {
            "verdes":   len([v for v in vs if v["clasificacion"] == "Alta viabilidad"]),
            "cautela":  len([v for v in vs if v["clasificacion"] == "Viabilidad media"]),
            "descarte": len([v for v in vs if v["clasificacion"] == "Descarte"])
        }

        # Almacenamiento LOCAL (sin IBM COS)
        output_path = os.path.join(_tmp_dir(), f"reporte_{req.analysis_id[:8]}.pdf")

        generator = URBANIAReportGenerator()
        generator.generate(pdf_dict, output_path)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=f"Reporte_Ejecutivo_{req.analysis_id[:8]}.pdf"
        )

    # JSON completo
    return {
        "analysis_id": data["analysis_id"],
        "metadata": data["metadata"],
        "scenarios": data["scenarios"],
        "executive_report": data["executive_report"]
    }
