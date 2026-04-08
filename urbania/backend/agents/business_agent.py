"""
URBANIA - Agente de Negocios (IBM Watsonx AI)
==============================================

Responsabilidades
-----------------
- Unificar score_demanda y score_riesgo.
- Calcular el Score de Viabilidad (SV) incorporando variables financieras 
  (ticket de inversion, factor potencial sectorial).
- Generar 3 escenarios financieros algoritmicos (Agresivo, Conservador, Equilibrado).
- Solicitar a Watsonx AI (Llama 3 70B o Granite 13B) redactar un reporte
  ejecutivo en lenguaje C-Suite con recomendaciones y justificaciones.

Variables de entorno (produccion):
    WATSONX_API_KEY      - IAM API key de IBM Cloud.
    WATSONX_PROJECT_ID   - ID del proyecto en IBM Watsonx.
    WATSONX_URL          - Base URL.
"""
from __future__ import annotations

import collections
import copy
import json
import logging
import math
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------

WATSONX_ENDPOINT   = "{base_url}/ml/v1/text/generation?version=2023-05-29"
IAM_TOKEN_ENDPOINT = "https://iam.cloud.ibm.com/identity/token"

# Segun el requerimiento, intentar usar Llama 3 70B, y usar Granite como fallback de prompt.
# Asumiremos la existencia del modelo "meta-llama/llama-3-1-70b-instruct" en watsonx, pero
# lo parametrizamos via variable o constante fallback.
WATSONX_MODEL_ID   = os.environ.get("WATSONX_MODEL_ID_BUSINESS", "ibm/granite-13b-instruct-v2")

MAX_RETRIES: int = 3
BACKOFF_BASE: float = 2.0

# Marcadores de formato de prompt (Asumimos formato prompt Granite standard para fallback
# Si es Llama 3, requerira su propio adapter. Por simplicidad usamos la interface generica).
_GRANITE_SYS_OPEN  = "<|system|>"
_GRANITE_USR_OPEN  = "<|user|>"
_GRANITE_RES_OPEN  = "<|assistant|>"
_GRANITE_EOT       = "<|end_of_text|>"

# Factor Potencial Sectorial (FP)
FACTOR_POTENCIAL = {
    "telecomunicaciones": 1.2,
    "seguridad": 1.0,
    "inmobiliario": 1.4,
}

# ---------------------------------------------------------------------------
# System prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
Eres URBANIA-BusinessAgent, un experto consultor estrategico y analista C-Suite.
Se te proporciona el analisis de 3 Escenarios Financieros (Agresivo, Conservador, Equilibrado) 
basado en inteligencia territorial, demanda y riesgo.

TU TAREA:
Produce un REPORTE EJECUTIVO para la alta direccion (C-Suite, Director de Expansion, CFO).
Evalua criticamente los escenarios y proporciona lineamientos estrategicos.

REGLAS ESTRICTAS:
1. Responde UNICAMENTE con un objeto JSON valido.
2. Formato EXACTO:
{{
  "resumen_ejecutivo": "string (2 parrafos ejecutivos)",
  "escenarios": [
    {{
      "nombre": "string (Agresivo, Conservador, Equilibrado)",
      "roi": "float (ej. 15.4)",
      "payback": "float (ej. 2.5)",
      "exposicion": "float (en millones MXN)",
      "recomendacion_narrativa": "string (1 parrafo con pros/contras)"
    }},
    ... los 3 escenarios
  ],
  "recomendacion_final": "string (cual elegir y por que detalladamente)",
  "advertencias": [ "string", "string", ... ],
  "proximos_pasos": [ "string", "string", ... ]
}}
3. NO generes texto adicional antes ni despues del JSON.
"""


# ---------------------------------------------------------------------------
# Funciones Helper Algoritmicas
# ---------------------------------------------------------------------------

def _extract_merged_features(demand_features: list[dict], risk_features: list[dict]) -> list[dict]:
    """Cruza features de demanda y riesgo por ID."""
    df_map = {f.get("id"): f for f in demand_features if "id" in f}
    rf_map = {f.get("id"): f for f in risk_features if "id" in f}
    
    merged = []
    for fid, d_feat in df_map.items():
        r_feat = rf_map.get(fid)
        if not r_feat:
            continue
        
        merged.append({
            "id": fid,
            "nombre": d_feat.get("nombre", "N/D"),
            "score_demanda": d_feat.get("score_demanda", 50.0),
            "score_riesgo": r_feat.get("score_riesgo", 50.0),
            "incidencia_raw": r_feat.get("incidencia_raw", 0)
        })
    return merged

def _calcular_viabilidad(sd: float, sr: float, fp: float, ti_norm: float) -> tuple[float, str]:
    """Calcula Score de Viabilidad (SV) y retorna el valor y categoria.
    Formula: SV = (SD * (1 - SR/100) * FP) / TI_normalizado
    """
    if ti_norm <= 0:
        ti_norm = 1.0 # protector fallback div zero
        
    sv = (sd * (1.0 - (sr / 100.0)) * fp) / float(ti_norm)
    sv = round(max(0.0, min(100.0, sv)), 2)
    
    if sv > 70:
        categoria = "Alta viabilidad"
    elif sv >= 40:
        categoria = "Viabilidad media"
    else:
        categoria = "Descarte"
        
    return sv, categoria

def _generar_escenario(nombre: str, sitios_candidatos: list[dict], params: dict, selector_func) -> dict:
    """Helper para estructurar la logica de cada escenario dado una funcion de seleccion."""
    ti_mxn           = params.get("ticket_inversion_mxn", 100000.0)
    vida_util        = params.get("vida_util_anios", 5)
    tasa_descuento   = params.get("tasa_descuento", 0.12)
    n_objetivo       = params.get("n_unidades_objetivo", 10)
    
    # 1. Selecion
    seleccionados = selector_func(sitios_candidatos, n_objetivo)
    
    # Si no hay candidatos tras el filtro, retornar vacio
    if not seleccionados:
        return {
            "nombre": nombre,
            "roi_estimado_5_anios": 0.0,
            "payback_period_anios": 0.0,
            "exposicion_max_riesgo_mxn": 0.0,
            "zonas_seleccionadas": [],
            "perdidas_evitadas_vs_aleatorio_mxn": 0.0
        }

    # 2. Metricas agregadas
    inversion_total = len(seleccionados) * ti_mxn
    riesgo_promedio = sum(s["score_riesgo"] for s in seleccionados) / len(seleccionados)
    demanda_promedio = sum(s["score_demanda"] for s in seleccionados) / len(seleccionados)
    
    # Proxy de flujo de caja anual (muy simplificado para SaaS B2B tool)
    # Flujo esperado = (Demanda/100) * Ticket * 0.40_margen_neto_esperado
    flujo_anual_esperado = (demanda_promedio / 100.0) * inversion_total * 0.40
    
    # ROI = (Beneficio_total - Inversion) / Inversion
    beneficio_total_bruto = flujo_anual_esperado * vida_util
    roi = ((beneficio_total_bruto - inversion_total) / inversion_total) * 100.0 if inversion_total > 0 else 0.0
    
    # Payback (simple)
    payback = inversion_total / flujo_anual_esperado if flujo_anual_esperado > 0 else 999.0
    
    # Exposicion al riesgo = Inversion_total * (Riesgo_promedio/100)
    exposicion = inversion_total * (riesgo_promedio / 100.0)
    
    # Perdida evitada proxy. Asume que base rate de riesgo es 50%.
    # si mitigamos a <50, esa diferencia * inversion es prevencion.
    perdida_evitada = inversion_total * max(0.0, (50.0 - riesgo_promedio) / 100.0)

    return {
        "nombre": nombre,
        "roi_estimado_5_anios": round(roi, 1),
        "payback_period_anios": round(payback, 1),
        "exposicion_max_riesgo_mxn": round(exposicion, 2),
        "zonas_seleccionadas": [s["id"] for s in seleccionados],
        "perdidas_evitadas_vs_aleatorio_mxn": round(perdida_evitada, 2)
    }

# ---------------------------------------------------------------------------
# Clase Principal BusinessAgent
# ---------------------------------------------------------------------------

class BusinessAgent:
    """Agente de Negocios URBANIA.
    
    Evalua viabilidad financiera integrando Demanda y Riesgo, genera escenarios
    y solicita narrativa ejecutiva a Watsonx AI.
    
    Args:
        use_fallback_only (bool): Si es True omite Watsonx y usa fallback mock.
    """
    
    def __init__(self, use_fallback_only: bool = False):
        self.use_fallback_only= use_fallback_only
        self._api_key: str    = os.environ.get("WATSONX_API_KEY", "")
        self._project_id: str = os.environ.get("WATSONX_PROJECT_ID", "")
        self._base_url: str   = os.environ.get(
            "WATSONX_URL", "https://us-south.ml.cloud.ibm.com"
        ).rstrip("/")
        
        logger.info(
            "BusinessAgent inicializado - fallback_only=%s watsonx_configured=%s",
            use_fallback_only,
            bool(self._api_key and self._project_id)
        )
        
    def generate_scenarios(self, demand_scores: list[dict], risk_scores: list[dict], params: dict) -> dict:
        """
        Produce escenarios financieros y reporte ejecutivo.
        
        Args:
            demand_scores: Output list de DemandAgent.
            risk_scores: Output list de RiskAgent.
            params: Dict con parametros financieros (ticket, tasa, etc.)
            
        Returns:
            Dict con 'escenarios' (algoritmicos), 'reporte_ejecutivo' y 'features_viabilidad'.
        """
        logger.info("BusinessAgent: generate_scenarios iniciado (%d params)", len(params))
        
        # 1. Variables de control
        sector = params.get("sector", "inmobiliario")
        fp     = FACTOR_POTENCIAL.get(sector, 1.0)
        ti_mxn = params.get("ticket_inversion_mxn", 500_000.0)
        ti_norm = ti_mxn / 1_000_000.0
        
        # 2. Merge y calcular Viabilidad por Manzana
        merged = _extract_merged_features(demand_scores, risk_scores)
        features_viables = []
        
        for m in merged:
            sv, cat = _calcular_viabilidad(m["score_demanda"], m["score_riesgo"], fp, ti_norm)
            m["score_viabilidad"] = sv
            m["categoria_viabilidad"] = cat
            features_viables.append(m)
            
        # 3. Modelado Algoritmico de 3 Escenarios
        
        # Escenario 1: Agresivo (top N zonas por SV, maximiza retorno)
        def _sel_agresivo(candidatos, n):
            c_sorted = sorted(candidatos, key=lambda x: x["score_viabilidad"], reverse=True)
            return c_sorted[:n]
            
        esc_agr = _generar_escenario("AGRESIVO", features_viables, params, _sel_agresivo)
        
        # Escenario 2: Conservador (score_riesgo < 20, luego por SV)
        def _sel_conservador(candidatos, n):
            c_filtrado = [c for c in candidatos if c["score_riesgo"] < 30.0]  # Ajuste zona Verde real
            c_sorted = sorted(c_filtrado, key=lambda x: x["score_viabilidad"], reverse=True)
            return c_sorted[:n]
            
        esc_con = _generar_escenario("CONSERVADOR", features_viables, params, _sel_conservador)
        
        # Escenario 3: Equilibrado (Sharpe ratio simplificado: SV / Max(Riesgo,1) )
        def _sel_equilibrado(candidatos, n):
            def sharpe_proxy(f):
                return f["score_viabilidad"] / max(f["score_riesgo"], 1.0)
            c_sorted = sorted(candidatos, key=sharpe_proxy, reverse=True)
            return c_sorted[:n]
            
        esc_equ = _generar_escenario("EQUILIBRADO", features_viables, params, _sel_equilibrado)
        
        escenarios_crudos = [esc_agr, esc_con, esc_equ]
        
        # 4. Solicitud a Watsonx (LLM Narrativa Ejecutiva)
        reporte_llm = None
        if not self.use_fallback_only and self._api_key and self._project_id:
            try:
                reporte_llm = self._call_watsonx(escenarios_crudos, params)
            except Exception as e:
                logger.error("Error Watsonx BusinessAgent: %s. Usando fallback.", e)
        
        if not reporte_llm:
            reporte_llm = self._generate_fallback_report(escenarios_crudos)
            reporte_llm["source"] = "fallback"
        else:
            reporte_llm["source"] = "watsonx"
        
        # Consolidar
        return {
            "datos_entrada": params,
            "escenarios_algoritmicos": escenarios_crudos,
            "reporte_ejecutivo": reporte_llm,
            "features_score_viabilidad": features_viables
        }

    def to_pdf_ready_dict(self, results: dict) -> dict:
        """Adapta el resultado de generacion para que el reporte PDF lo consuma directo."""
        rep = results.get("reporte_ejecutivo", {})
        
        return {
            "business_resumen": rep.get("resumen_ejecutivo", ""),
            "business_escenarios": rep.get("escenarios", []),
            "business_recomendacion": rep.get("recomendacion_final", ""),
            "business_advertencias": rep.get("advertencias", []),
            "business_pasos": rep.get("proximos_pasos", []),
            "business_source": rep.get("source", "fallback")
        }
        
    # --- Interfaz Interna Watsonx ---
        
    def _call_watsonx(self, escenarios: list[dict], params: dict) -> dict:
        system_p = _SYSTEM_PROMPT_TEMPLATE
        
        data_context = json.dumps({
            "parametros_cliente": params,
            "calculo_escenarios": escenarios
        }, indent=2, ensure_ascii=False)
        
        user_p = f"Genera el reporte ejecutivo JSON basado en estos datos algoritmicos:\n{data_context}\n"
        combined = _GRANITE_SYS_OPEN + "\n" + system_p + "\n" + _GRANITE_USR_OPEN + "\n" + user_p + "\n" + _GRANITE_RES_OPEN + "\n"
        
        raw_resp = _call_watsonx_rest(
            combined_input=combined,
            api_key=self._api_key,
            project_id=self._project_id,
            base_url=self._base_url
        )
        
        return _parse_business_response(raw_resp)

    def _generate_fallback_report(self, escenarios: list[dict]) -> dict:
        # Crea un mock structure en caso de error REST
        return {
            "resumen_ejecutivo": "El analisis multivariable de demanda y riesgo refleja oportunidades segmentadas. El escenario equilibrado presenta la mejor relacion riesgo-rendimiento mitigando factores operacionales colindantes.",
            "escenarios": [
                {
                   "nombre": e["nombre"],
                   "roi": e["roi_estimado_5_anios"],
                   "payback": e["payback_period_anios"],
                   "exposicion": float(e["exposicion_max_riesgo_mxn"]) / 1_000_000.0,
                   "recomendacion_narrativa": f"Proyeccion algoritmica automatica para perfil {e['nombre']}."
                } for e in escenarios
            ],
            "recomendacion_final": "Algoritmicamente, sugerimos el Escenario EQUILIBRADO por presentar un factor Sharpe interno superior.",
            "advertencias": ["Fallback algoritmico activo, analisis cualitativo IA no disponible.", "Verificar parametros de ticket Inversion in situ."],
            "proximos_pasos": ["Validacion tecnica en campo.", "Auditoria de iluminacion en zonas de descarte colindantes."]
        }


# ---------------------------------------------------------------------------
# Helpers de Red y Parseo (Reuso adaptado)
# ---------------------------------------------------------------------------

def _call_watsonx_rest(combined_input: str, api_key: str, project_id: str, base_url: str) -> dict:
    endpoint = WATSONX_ENDPOINT.format(base_url=base_url)
    try:
        response = httpx.post(
            IAM_TOKEN_ENDPOINT,
            data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        response.raise_for_status()
        iam_token = response.json().get("access_token")
    except Exception as exc:
        raise RuntimeError(f"IAM Token fail: {exc}")

    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    # Parametros para Tareas Generativas de Parrafos Largos
    payload = {
        "model_id": WATSONX_MODEL_ID,
        "project_id": project_id,
        "input": combined_input,
        "parameters": {
            "max_new_tokens": 1500,  # Bastante texto esperado
            "temperature": 0.2,      
            "stop_sequences": [_GRANITE_EOT, "```"],
            "repetition_penalty": 1.1
        },
    }

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("Agent Negocios HTTP err: %s", exc)
            last_exc = exc
            time.sleep(BACKOFF_BASE ** attempt)
            
    raise RuntimeError(f"Watsonx API exhausta tras {MAX_RETRIES} ints: {last_exc}")

def _parse_business_response(raw: dict) -> dict:
    try:
        text: str = raw["results"][0]["generated_text"].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object bounds found.")
        json_obj = json.loads(text[start:end+1])
    except Exception as e:
        logger.error("Parse Business LLM text fail: %s. Texto: %s", e, text[:250] if 'text' in locals() else 'N/A')
        raise ValueError(f"Fallo parsing LLM a JSON: {e}")
        
    return json_obj
