"""
URBANIA - API REST (FastAPI)
============================

Punto de entrada principal para URBANIA. Orquesta la ejecucion en paralelo de 
agentes de inteligencia territorial (Demanda, Riesgo, Negocios) y expone
los endpoints requeridos por el frontend (React/Leaflet).
"""
import asyncio
import copy
import logging
import os
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Importaciones Internas (Agentes y Utils) ──────────────────────────────
from data.ingest import flag_production_sources, load_mock_fixture, run_ingestion
from agents.demand_agent import DemandAgent
from agents.risk_agent import RiskAgent
from agents.business_agent import BusinessAgent

# ── 1. Configuracion de Logging ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("urbania.api")

# ── 2. Instancia de la Aplicacion FastAPI ─────────────────────────────────
app = FastAPI(
    title="URBANIA API REST",
    description="Motor B2B de inteligencia territorial con IBM Watsonx AI.",
    version="1.0.0",
    docs_url="/docs",     # Swagger UI habilitado por defecto
    redoc_url="/redoc",
)

# ── 3. Middlewares (CORS y Logging de peticiones) ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Vite dev host
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"START {request.method} {request.url.path}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"COMPLETE {response.status_code} {request.method} {request.url.path} in {process_time:.3f}s")
    return response


# ── 4. Almacenamiento Coche (In-Memory) ───────────────────────────────────
# Diccionario para preservar los ultimos 20 analisis en memoria local.
# Útil para exportar el GeoJSON o el reporte ejecutivo en requests subsecuentes.
MAX_HISTORY = 20
_analysis_history: OrderedDict[str, dict] = OrderedDict()


# ── 5. Modelos Pydantic (Validacion de Entradas) ──────────────────────────

class BusinessParams(BaseModel):
    """Parametros financieros ingresados por el usuario desde la UI."""
    ticket_inversion_mxn: float = Field(..., gt=0, description="Costo unitario por despliegue.")
    vida_util_anios: int = Field(..., gt=0, description="Vida util estimada del activo.")
    tasa_descuento: float = Field(..., gt=0, lt=1, description="Tasa de descuento anual (WACC).")
    n_unidades_objetivo: int = Field(..., gt=0, description="Cantidad de sitios priorizados.")

class AnalyzeRequest(BaseModel):
    """Cuerpo de la peticion principal para orquestar los agentes."""
    zone_polygon: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Geometría GeoJSON Polygon opcional. Nulo procesa todo el mapa."
    )
    sector: str = Field(
        ..., 
        pattern="^(telecomunicaciones|seguridad|inmobiliario)$",
        description="Sector industrial objetivo."
    )
    params: BusinessParams

class ExportGeojsonRequest(BaseModel):
    analysis_id: str = Field(..., description="ID unico del analisis retornado por el API.")

class ExportReportRequest(BaseModel):
    analysis_id: str = Field(..., description="ID unico del analisis retornado por el API.")
    format: str = Field(
        default="json", 
        pattern="^(json|pdf_ready)$",
        description="Formato de salida requerido para el reporte ejecutivo. json (raw) o pdf_ready (plano)."
    )


# ── 6. Endpoints de la API ────────────────────────────────────────────────

@app.post("/api/v1/analyze", summary="Ejecutar Analisis de Inteligencia Territorial")
async def analyze_zone(req: AnalyzeRequest):
    """
    Orquesta los modulos de Ingesta, Agente de Demanda, Agente de Riesgo, y Agente de Negocios.
    El analizador paralelo agiliza el scoring geografico, que culmina con una sintesis C-Suite.
    """
    analysis_id = str(uuid.uuid4())
    logger.info(f"Initiating /analyze process | ID: {analysis_id} | Sector: {req.sector}")
    
    try:
        # A) INGESTA: Filtrar espacialmente manzanas del target y normalizar (M1)
        zone_arg = req.zone_polygon or {}
        features_norm = await asyncio.to_thread(run_ingestion, zone_arg, req.sector)
        
        if not features_norm:
            raise HTTPException(
                status_code=400, 
                detail="El polígono delimitado no intersecta con ninguna de las manzanas disponibles."
            )
            
        is_prod_mode = flag_production_sources()
        
        # B) INIT AGENTES: Usamos un modo fallback automatizado si URBANIA_PROD_MODE != 1
        demand_agent = DemandAgent(sector=req.sector, use_fallback_only=not is_prod_mode)
        risk_agent = RiskAgent(use_fallback_only=not is_prod_mode)
        business_agent = BusinessAgent(use_fallback_only=not is_prod_mode)
        
        # C) SCORING PARALELO: Agente Demanda || Agente Riesgo Operativo
        logger.info(f"Paralelizando {len(features_norm)} features a Watsonx / Fallbacks...")
        demand_scores, risk_scores = await asyncio.gather(
            asyncio.to_thread(demand_agent.score, features_norm, req.sector),
            asyncio.to_thread(risk_agent.score, features_norm)
        )
        
        # D) SINTESIS EJECUTIVA: Toma resultados combinados y proyecta en modelo financiero
        logger.info("Consolidando Score de Viabilidad Financiera y Narrativa C-Suite...")
        
        b_params = req.params.model_dump() # dict pydantic >= 2
        b_params["sector"] = req.sector
        
        business_results = await asyncio.to_thread(
            business_agent.generate_scenarios, 
            demand_scores, 
            risk_scores, 
            b_params
        )
        
        # E) POST-PROCESO GEOJSON: Reinterpretar a capas Leaflet consumibles
        # Cargamos el archivo nativo desde su origen para mantener la geometria original sin normalizacion
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        original_geojson = await asyncio.to_thread(load_mock_fixture, os.path.join(data_dir, "mock_fixture.json"))
        
        demand_geojson = await asyncio.to_thread(demand_agent.to_geojson, demand_scores, original_geojson)
        risk_geojson = await asyncio.to_thread(risk_agent.generate_risk_geojson, risk_scores, original_geojson)
        
        # Extraer compact list top viability
        viables = []
        for feat in business_results.get("features_score_viabilidad", []):
            viables.append({
                "id": feat["id"],
                "score_viabilidad": feat["score_viabilidad"],
                "clasificacion": feat["categoria_viabilidad"]
            })
            
        # Preparando objeto final de respuesta
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
                "zone_filtered": bool(zone_arg)
            }
        }
        
        # Gestionar la cache rotativa de 20 slots
        if len(_analysis_history) >= MAX_HISTORY:
            # Drop el elemento mas antiguo
            _analysis_history.popitem(last=False)
        _analysis_history[analysis_id] = response_data
        
        logger.info(f"Proceso finalizado. Analysis ID {analysis_id} preparado y devuelto.")
        return response_data

    except Exception as e:
        logger.error(f"Error procesando analysis: {e}", exc_info=True)
        # Re-raise standard http si no lo es
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Error nativo orquestando request: {str(e)}")


@app.get("/api/v1/mock-zone", summary="Obtener GeoJSON del fixture original crudo")
def get_mock_zone():
    """
    Retorna el FeatureCollection de CDMX base usado en Demo/Mock mode, util para
    poblar el mapa inicial en el Frontend.
    """
    try:
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        return load_mock_fixture(os.path.join(data_dir, "mock_fixture.json"))
    except Exception as e:
        logger.error(f"Error leyendo mock_fixture: {e}")
        raise HTTPException(status_code=500, detail="El archivo base (fixture) no existe en la carpeta requerida.")


@app.get("/api/v1/health", summary="Status API Check incl. conectividad Watsonx")
def health_check():
    """Comprueba el entorno, ping a los modelos y estatus general del API."""
    import urllib.request
    
    prod_mode = flag_production_sources()
    wx_url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    
    wx_ok = False
    if prod_mode:
        try:
            code = urllib.request.urlopen(wx_url, timeout=3.0).getcode()
            wx_ok = (code is not None and code < 500)
        except Exception as e:
            logger.warning(f"Health Check: Watsonx ping falido -> {e}")
            wx_ok = False
    else:
        wx_ok = True  # En fallback damos por bueno el servicio "mental" algoritmico
        
    return {
        "status": "ok",
        "watsonx_prod_enabled": prod_mode,
        "watsonx_network_ok": wx_ok,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/v1/export/geojson", summary="Exportar Resultados completos del mapa")
async def export_geojson(req: ExportGeojsonRequest):
    """
    Exporta un GeoJSON consolidado unificando las properties de Riesgo, Demanda y Negocio.
    """
    data = _analysis_history.get(req.analysis_id)
    if not data:
        raise HTTPException(
            status_code=404, 
            detail="Analysis ID no encontrado. Puede que haya expirado la cache de memoria."
        )
    
    # Iniciar la copia profunda basada en Demanda (que guarda geo y props de demand_agent)
    export_json = copy.deepcopy(data["demand_geojson"])
    
    # Mapas de acceso Rapido para Fusion
    risk_map = {f["id"]: f for f in data["risk_geojson"].get("features", []) if "id" in f}
    viability_map = {f["id"]: f for f in data["viability_scores"]}
    
    for feat in export_json.get("features", []):
        props = feat.setdefault("properties", {})
        fid = props.get("id") or feat.get("id")
        
        # Acoplar Riesgo
        r_node = risk_map.get(fid)
        if r_node:
            r_props = r_node.get("properties", {})
            props["score_riesgo"]               = r_props.get("score_riesgo")
            props["clasificacion_riesgo"]       = r_props.get("clasificacion")
            props["color_leaflet_riesgo"]       = r_props.get("color_leaflet")
            props["factores_riesgo"]            = r_props.get("factores_riesgo")
            props["recomendaciones_mitigacion"] = r_props.get("recomendaciones_mitigacion")
            props["razon_descarte"]             = r_props.get("razon_descarte")
            
        # Acoplar Negocio
        v_node = viability_map.get(fid)
        if v_node:
            props["score_viabilidad"]       = v_node.get("score_viabilidad")
            props["clasificacion_negocios"] = v_node.get("clasificacion")

    # Devolverlo como un attachment binario de descarga si queremos
    # Por defecto devolvemos JSON y el Frontend maneja un Blob().
    return JSONResponse(
        content=export_json, 
        headers={"Content-Disposition": f'attachment; filename="urbania_analysis_{req.analysis_id}.geojson"'}
    )


@app.post("/api/v1/export/report", summary="Exportar Extracto C-Suite de Reporte")
async def export_report(req: ExportReportRequest):
    """
    Retorna los datos narrativos del Agente de Negocios en JSON crudo o plano,  
    listos para ser inyectados en la generacion nativa de PDF Executive de Urbania.
    """
    data = _analysis_history.get(req.analysis_id)
    if not data:
        raise HTTPException(status_code=404, detail="Analysis ID no encontrado.")
        
    if req.format == "pdf_ready":
        # Formateado plano simplificado consumible directo por reportlab logic
        dummy_agent = BusinessAgent(use_fallback_only=True)
        pdf_dict = dummy_agent.to_pdf_ready_dict({"reporte_ejecutivo": data["executive_report"]})
        
        pdf_dict.update({
            "analysis_id": data["analysis_id"],
            "metadata": data["metadata"]
        })
        return pdf_dict
        
    # Salida por Defecto JSON completo
    return {
        "analysis_id": data["analysis_id"],
        "metadata": data["metadata"],
        "scenarios": data["scenarios"],
        "executive_report": data["executive_report"]
    }
