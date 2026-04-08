import os
import sys
import json
import time
import uuid
import asyncio
from datetime import datetime, timezone

# IBM Cloud Functions expone los paquetes instalados en 'packages'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'packages')))

# Importar agentes (se copiaran durante deploy.sh)
try:
    from data.ingest import run_ingestion
    from agents.demand_agent import DemandAgent
    from agents.risk_agent import RiskAgent
    from agents.business_agent import BusinessAgent
except Exception as e:
    print(f"Warning: agents import failed locally {e}")

def get_cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

async def async_analyze(sector, b_params, zone_arg, timeout_limit, is_prod_mode):
    start_time = time.time()
    
    # M1: Ingesta
    features_norm = run_ingestion(zone_arg, sector)
    if not features_norm:
        return {"error": "No hay manzanas en el area delimitada."}

    # Inicializar agentes
    demand_agent = DemandAgent(sector=sector, use_fallback_only=not is_prod_mode)
    risk_agent = RiskAgent(use_fallback_only=not is_prod_mode)
    business_agent = BusinessAgent(use_fallback_only=not is_prod_mode)

    # Revisar timeout
    if time.time() - start_time > timeout_limit:
        return {"error": "Timeout inminente abortando antes de scores."}

    # Scoring Paralelo (Limitamos asyncio await si estamos con prisa)
    demand_scores, risk_scores = await asyncio.gather(
        asyncio.to_thread(demand_agent.score, features_norm, sector),
        asyncio.to_thread(risk_agent.score, features_norm)
    )

    if time.time() - start_time > timeout_limit:
        return {"error": "Timeout inminente abortando antes de business."}

    # Business
    b_params["sector"] = sector
    business_results = business_agent.generate_scenarios(demand_scores, risk_scores, b_params)

    # Construir response
    # Omitimos carga pesada de GeoJSON completo aqui para no exceder limits (mocked en backend local)
    # Devuelvo estricto
    
    viables = []
    for feat in business_results.get("features_score_viabilidad", []):
        viables.append({
            "id": feat["id"],
            "score_viabilidad": feat["score_viabilidad"],
            "clasificacion": feat["categoria_viabilidad"]
        })

    response_data = {
        "analysis_id": str(uuid.uuid4()),
        "viability_scores": viables,
        "scenarios": business_results.get("escenarios_algoritmicos", []),
        "executive_report": business_results.get("reporte_ejecutivo", {}),
        "metadata": {
            "sector": sector,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_manzanas_analizadas": len(features_norm),
            "timeout_warning": False
        }
    }
    
    return response_data

def main(params):
    """
    Entrypoint IBM Cloud Functions.
    Recibe: zone_polygon, sector, parameters.
    """
    # 1. CORS Preflight Support and Headers Check
    if params.get("__ow_method") == "options":
        return {"headers": get_cors_headers(), "statusCode": 204, "body": ""}
        
    # Variables de entorno inyectadas como params
    os.environ["WATSONX_API_KEY"] = params.get("WATSONX_API_KEY", "")
    os.environ["WATSONX_PROJECT_ID"] = params.get("WATSONX_PROJECT_ID", "")
    prod_mode = params.get("URBANIA_PROD_MODE", "false").lower() == "true"
    
    # Timeout control
    timeout_limit = 50.0  # IBM action limit is 60s
    start_time = time.time()
    
    body = params
    
    sector = body.get("sector", "telecomunicaciones")
    b_params = body.get("params", {
        "ticket_inversion_mxn": 500000, 
        "vida_util_anios": 5, 
        "tasa_descuento": 0.12, 
        "n_unidades_objetivo": 10
    })
    zone_polygon = body.get("zone_polygon", {})

    try:
        # Run asyncio wrapper
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # We can implement an asyncio.wait_for wrapper around it
        task = loop.create_task(async_analyze(sector, b_params, zone_polygon, timeout_limit, prod_mode))
        result = loop.run_until_complete(asyncio.wait_for(task, timeout=timeout_limit))
        
        return {
            "headers": get_cors_headers(),
            "statusCode": 200,
            "body": result
        }

    except asyncio.TimeoutError:
        return {
            "headers": get_cors_headers(),
            "statusCode": 206, # Partial Content / Timeout warning
            "body": {
                "error": "El computo tomaba demasiado. Interrumpido a los 50s limite de Cloud Functions.",
                "timeout": True
            }
        }
    except Exception as e:
        return {
            "headers": get_cors_headers(),
            "statusCode": 500,
            "body": {"error": str(e)}
        }
