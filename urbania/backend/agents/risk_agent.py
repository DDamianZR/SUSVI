"""
URBANIA - Agente de Riesgo Operativo (IBM Watsonx AI)
======================================================

Responsabilidades
-----------------
- Calcular el score_riesgo [0-100] de cada manzana combinando:
    incidencia_delictiva_snsp (50%), deficit_iluminacion (25%),
    indice_accesibilidad_logistica inverso (25%).
- Clasificar cada manzana en VERDE / CAUTELA / DESCARTE.
- Enriquecer el GeoJSON con colores Leaflet y metadatos Watsonx.
- Proporcionar recomendaciones de mitigacion (CAUTELA) o
  razon de descarte ejecutiva (DESCARTE) via Granite 13B.

Modo de operacion
-----------------
- Produccion  : Watsonx confirma/ajusta el score y genera narrativa.
- Fallback/demo: clasificacion algoritmica pura sin narrativa LLM.

Variables de entorno (produccion):
    WATSONX_API_KEY      - IAM API key de IBM Cloud.
    WATSONX_PROJECT_ID   - ID del proyecto en IBM Watsonx.
    WATSONX_URL          - Base URL (default: https://us-south.ml.cloud.ibm.com).
"""
from __future__ import annotations

import copy
import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------

WATSONX_ENDPOINT = "{base_url}/ml/v1/text/generation?version=2023-05-29"
IAM_TOKEN_ENDPOINT = "https://iam.cloud.ibm.com/identity/token"
WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"

MAX_RETRIES: int = 3
BACKOFF_BASE: float = 2.0
BATCH_SIZE: int = 20           # lotes mas pequenos: la narrativa es mas larga

# Marcadores de formato Granite 13B Instruct
_GRANITE_SYS_OPEN  = "<|system|>"
_GRANITE_USR_OPEN  = "<|user|>"
_GRANITE_RES_OPEN  = "<|assistant|>"
_GRANITE_EOT       = "<|end_of_text|>"

# ---------------------------------------------------------------------------
# Pesos del Score de Riesgo Operativo
# ---------------------------------------------------------------------------

#: Pesos para el calculo del score de riesgo (deben sumar 1.0).
RISK_WEIGHTS: dict[str, float] = {
    # incidencia_delictiva_snsp_norm: ya invertida en ingest
    # (mas delitos = norm MAS ALTA en risk_agent, pues aqui es riesgo directo)
    "incidencia_delictiva_snsp_norm": 0.50,
    # deficit_iluminacion = 100 - iluminacion_publica_norm
    "_deficit_iluminacion_":          0.25,
    # indice_accesibilidad_inv = 100 - accesibilidad_logistica_norm
    "_accesibilidad_inv_":            0.25,
}

# ---------------------------------------------------------------------------
# Clasificacion y colores
# ---------------------------------------------------------------------------

#: Umbrales de clasificacion de riesgo.
RISK_THRESHOLDS: dict[str, tuple[float, float]] = {
    "VERDE":    (0.0,  30.0),
    "CAUTELA":  (30.0, 60.0),
    "DESCARTE": (60.0, 100.0),
}

#: Colores Leaflet por clasificacion (hex).
RISK_COLORS: dict[str, str] = {
    "VERDE":    "#22c55e",
    "CAUTELA":  "#f59e0b",
    "DESCARTE": "#ef4444",
}

# ---------------------------------------------------------------------------
# Few-shot examples para el system prompt
# ---------------------------------------------------------------------------

_FEW_SHOT: str = json.dumps(
    [
        {
            "id": "MZ-006",
            "score_riesgo": 88.5,
            "clasificacion": "DESCARTE",
            "factores_riesgo": [
                {"factor": "Incidencia delictiva: 420 delitos anuales (percentil 95)", "peso_relativo": "50%"},
                {"factor": "Iluminacion publica: solo 20% de cobertura, deficit critico", "peso_relativo": "25%"},
                {"factor": "Accesibilidad logistica: score 40/100, rutas de evacuacion limitadas", "peso_relativo": "25%"},
            ],
            "recomendaciones_mitigacion": [],
            "razon_descarte": (
                "La manzana Tepito Norte acumula el maximo nivel de riesgo operativo: "
                "420 delitos anuales la ubican en el percentil 95 de incidencia violenta, "
                "combinado con una cobertura de iluminacion del 20% que potencia la "
                "inseguridad nocturna. La accesibilidad logistica de 40/100 dificulta "
                "respuestas de emergencia. Se recomienda descartar cualquier inversion "
                "hasta que intervencion gubernamental reduzca la incidencia al menos un 60%."
            ),
        },
        {
            "id": "MZ-001",
            "score_riesgo": 8.2,
            "clasificacion": "VERDE",
            "factores_riesgo": [
                {"factor": "Incidencia delictiva: 28 delitos anuales, zona controlada", "peso_relativo": "50%"},
                {"factor": "Iluminacion publica: 95% de cobertura, excelente", "peso_relativo": "25%"},
                {"factor": "Accesibilidad logistica: score 92/100, multiples rutas", "peso_relativo": "25%"},
            ],
            "recomendaciones_mitigacion": [],
            "razon_descarte": "",
        },
        {
            "id": "MZ-034",
            "score_riesgo": 47.3,
            "clasificacion": "CAUTELA",
            "factores_riesgo": [
                {"factor": "Incidencia delictiva: 142 delitos anuales en zona turistica", "peso_relativo": "50%"},
                {"factor": "Iluminacion publica: 55% de cobertura, mejorable", "peso_relativo": "25%"},
                {"factor": "Accesibilidad logistica: score 70/100, aceptable", "peso_relativo": "25%"},
            ],
            "recomendaciones_mitigacion": [
                "Negociar con municipio programa de luminarias LED en 3 cuadras perimetrales para reducir incidencia nocturna.",
                "Contratar seguridad privada compartida con establecimientos colindantes para optimizar costo-beneficio.",
            ],
            "razon_descarte": "",
        },
    ],
    ensure_ascii=False,
    indent=2,
)

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
Eres URBANIA-RiskAgent, analista de riesgo operativo urbano.
Se te proporcionan manzanas con su score_riesgo calculado algoritmicamente [0-100].

TU TAREA:
1. Confirmar o ajustar el score_riesgo (ajuste maximo: +/-5 puntos, con justificacion).
2. Identificar 2-3 factores de riesgo especificos con su peso relativo.
3. Para clasificacion CAUTELA: generar 2 recomendaciones de mitigacion concretas y accionables.
4. Para clasificacion DESCARTE: redactar 1 parrafo ejecutivo explicando por que no invertir.
5. Para clasificacion VERDE: arrays vacios en recomendaciones_mitigacion y razon_descarte.

CLASIFICACION:
- VERDE   : score_riesgo < 30   (inversion segura)
- CAUTELA : 30 <= score <= 60   (requiere mitigacion)
- DESCARTE: score_riesgo > 60   (no invertir)

REGLAS ESTRICTAS:
1. Responde UNICAMENTE con array JSON valido. SIN texto fuera del JSON.
2. Cada objeto debe tener EXACTAMENTE las claves:
   - "id"                        : string
   - "score_riesgo"              : float con 1 decimal [0.0-100.0]
   - "clasificacion"             : "VERDE" | "CAUTELA" | "DESCARTE"
   - "factores_riesgo"           : array de 2-3 objetos {factor: string, peso_relativo: string}
   - "recomendaciones_mitigacion": array de strings (2 para CAUTELA, [] para otros)
   - "razon_descarte"            : string (parrafo para DESCARTE, "" para otros)
3. El ajuste al score no puede exceder +/-5 puntos del valor recibido.

EJEMPLO DE OUTPUT:
{few_shot}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify(score: float) -> str:
    """Clasifica un score de riesgo en VERDE / CAUTELA / DESCARTE.

    Args:
        score: Score de riesgo en [0.0, 100.0].

    Returns:
        String con la clasificacion.
    """
    if score < 30.0:
        return "VERDE"
    if score <= 60.0:
        return "CAUTELA"
    return "DESCARTE"


def _compute_raw_risk(feat: dict) -> float:
    """Calcula el score de riesgo puro desde campos normalizados.

    Formula:
        score = (incidencia_norm * 0.50)
              + ((100 - iluminacion_norm) * 0.25)
              + ((100 - accesibilidad_norm) * 0.25)

    Nota: incidencia_delictiva_snsp_norm tal como llega de ingest.py
    esta INVERTIDA (menos delitos = mayor norm). Aqui la RE-invertimos
    para que mas delitos = mayor riesgo.

    Args:
        feat: Dict normalizado de ingest.normalize_features.

    Returns:
        Score de riesgo [0.0, 100.0].
    """
    # ingest invierte incidencia: norm alta = area segura.
    # Para riesgo necesitamos lo opuesto: norm baja = area peligrosa = riesgo alto.
    incidencia_norm = float(feat.get("incidencia_delictiva_snsp_norm", 50.0))
    # Re-invertimos: peligro = 100 - norm_segura
    riesgo_incidencia = 100.0 - incidencia_norm

    iluminacion_norm  = float(feat.get("iluminacion_publica_norm", 50.0))
    deficit_ilum      = 100.0 - iluminacion_norm

    accesibilidad_norm = float(feat.get("accesibilidad_logistica_norm", 50.0))
    deficit_acceso     = 100.0 - accesibilidad_norm

    score = (
        riesgo_incidencia * RISK_WEIGHTS["incidencia_delictiva_snsp_norm"]
        + deficit_ilum    * RISK_WEIGHTS["_deficit_iluminacion_"]
        + deficit_acceso  * RISK_WEIGHTS["_accesibilidad_inv_"]
    )
    return round(min(max(score, 0.0), 100.0), 2)


def _build_fallback_record(feat: dict, score: float, clasif: str) -> dict:
    """Construye un record de riesgo completo en modo fallback (sin LLM).

    Args:
        feat:   Dict normalizado.
        score:  Score de riesgo calculado.
        clasif: Clasificacion ("VERDE" | "CAUTELA" | "DESCARTE").

    Returns:
        Dict con todas las claves del schema de salida.
    """
    factores = [
        {
            "factor": f"Incidencia delictiva: {feat.get('incidencia_delictiva_snsp_raw', 'N/D')} delitos/ano",
            "peso_relativo": "50%",
        },
        {
            "factor": f"Deficit de iluminacion: {100 - float(feat.get('iluminacion_publica_norm', 50)):.0f}% sin cobertura",
            "peso_relativo": "25%",
        },
        {
            "factor": f"Accesibilidad logistica inversa: {feat.get('accesibilidad_logistica_raw', 'N/D') }/100",
            "peso_relativo": "25%",
        },
    ]

    recomendaciones: list[str] = []
    razon_descarte = ""

    if clasif == "CAUTELA":
        recomendaciones = [
            "Evaluar mejora de iluminacion publica con programa LED municipal.",
            "Contratar seguridad privada compartida con negocios colindantes.",
        ]
    elif clasif == "DESCARTE":
        tipo = feat.get("tipo_delito_predominante", "N/D")
        razon_descarte = (
            f"Score de riesgo {score:.1f}/100 en zona DESCARTE. "
            f"Delito predominante: {tipo}. "
            f"Incidencia de {feat.get('incidencia_delictiva_snsp_raw', '?')} delitos anuales "
            f"combinada con iluminacion del {feat.get('iluminacion_publica_raw', '?'):.0f}% "
            f"y acceso logistico limitado ({feat.get('accesibilidad_logistica_raw', '?'):.0f}/100). "
            "Se recomienda no invertir hasta que condiciones estructurales mejoren."
        )

    return {
        "id":                         feat.get("id"),
        "nombre":                     feat.get("nombre"),
        "score_riesgo":               score,
        "clasificacion":              clasif,
        "color_leaflet":              RISK_COLORS[clasif],
        "factores_riesgo":            factores,
        "recomendaciones_mitigacion": recomendaciones,
        "razon_descarte":             razon_descarte,
        "score_source":               "fallback",
        # Campos extra utiles para el dashboard
        "incidencia_raw":             feat.get("incidencia_delictiva_snsp_raw"),
        "tipo_delito":                feat.get("tipo_delito_predominante", "N/D"),
        "iluminacion_raw":            feat.get("iluminacion_publica_raw"),
        "accesibilidad_raw":          feat.get("accesibilidad_logistica_raw"),
    }


def _slim_for_risk(features: list[dict]) -> list[dict]:
    """Proyecta solo campos relevantes para el prompt de riesgo.

    Args:
        features: Features normalizadas con campos _norm y _raw.

    Returns:
        Lista de dicts slim con id, nombre y campos de riesgo.
    """
    slim = []
    for f in features:
        slim.append({
            "id":                         f.get("id"),
            "nombre":                     f.get("nombre"),
            "score_riesgo_algoritmico":   f.get("_pre_score_riesgo_", 50.0),
            "clasificacion_algoritmica":  f.get("_pre_clasif_", "CAUTELA"),
            "incidencia_delictiva_anual": f.get("incidencia_delictiva_snsp_raw"),
            "iluminacion_publica_pct":    f.get("iluminacion_publica_raw"),
            "accesibilidad_logistica":    f.get("accesibilidad_logistica_raw"),
            "tipo_delito_predominante":   f.get("tipo_delito_predominante"),
        })
    return slim


# ---------------------------------------------------------------------------
# Clase principal: RiskAgent
# ---------------------------------------------------------------------------


class RiskAgent:
    """Agente de Riesgo Operativo URBANIA (IBM Watsonx AI - Granite 13B).

    Calcula el score_riesgo [0-100] de cada manzana normalizada mediante
    promedio ponderado y solicita a Watsonx confirmacion/ajuste + narrativa.
    Si Watsonx no esta disponible, aplica clasificacion algoritmica pura.

    Componentes del score:
        incidencia_delictiva_snsp : 50%  (re-invertida desde ingest)
        deficit_iluminacion       : 25%  (100 - iluminacion_publica_norm)
        deficit_accesibilidad     : 25%  (100 - accesibilidad_logistica_norm)

    Clasificacion:
        VERDE    : score < 30
        CAUTELA  : 30 <= score <= 60
        DESCARTE : score > 60

    Args:
        use_fallback_only: Si True, omite Watsonx (demo/testing).

    Example::

        agent = RiskAgent()
        scored = agent.score(normalized_features)
        geojson = agent.generate_risk_geojson(scored, original_fixture)
    """

    def __init__(self, use_fallback_only: bool = False) -> None:
        self.use_fallback_only: bool = use_fallback_only

        self._api_key: str    = os.environ.get("WATSONX_API_KEY", "")
        self._project_id: str = os.environ.get("WATSONX_PROJECT_ID", "")
        self._base_url: str   = os.environ.get(
            "WATSONX_URL", "https://us-south.ml.cloud.ibm.com"
        ).rstrip("/")

        logger.info(
            "RiskAgent inicializado — fallback_only=%s  watsonx_configured=%s",
            use_fallback_only,
            bool(self._api_key and self._project_id),
        )

    # ── API publica ─────────────────────────────────────────────────────────

    def score(self, features: list[dict]) -> list[dict]:
        """Calcula el score de riesgo para una lista de manzanas normalizadas.

        Flujo:
        1. Calcula score algoritmico y clasificacion previa.
        2. Si Watsonx disponible: envia para confirmacion/ajuste y narrativa.
        3. Si Watsonx falla: usa clasificacion algoritmica pura (fallback).

        Args:
            features: Dicts normalizados de ingest.normalize_features.
                      Deben contener campos _norm y _raw.

        Returns:
            Lista de dicts por manzana con:
            - id, nombre (str)
            - score_riesgo (float, 0-100)
            - clasificacion ("VERDE" | "CAUTELA" | "DESCARTE")
            - color_leaflet (str, hex)
            - factores_riesgo (list[dict])
            - recomendaciones_mitigacion (list[str])
            - razon_descarte (str)
            - score_source ("watsonx" | "fallback")
            - incidencia_raw, tipo_delito, iluminacion_raw, accesibilidad_raw

        Raises:
            ValueError: Si features esta vacia.
        """
        if not features:
            raise ValueError("La lista de features no puede estar vacia.")

        logger.info("RiskAgent.score — analizando %d manzanas.", len(features))

        # Paso 1: calcular scores algoritmicos y anotarlos en cada feature
        pre_scored = self._pre_score(features)

        # Paso 2: intentar Watsonx (confirmacion + narrativa)
        if not self.use_fallback_only and self._api_key and self._project_id:
            try:
                return self._score_with_watsonx(pre_scored)
            except EnvironmentError:
                logger.warning("Credenciales Watsonx invalidas — usando fallback.")
            except RuntimeError as exc:
                logger.warning("Watsonx fallo (%s) — usando fallback.", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Error inesperado en Watsonx (%s: %s) — usando fallback.",
                    type(exc).__name__,
                    exc,
                )

        # Paso 3: fallback
        logger.info("RiskAgent: usando fallback algoritmico.")
        return self._score_fallback(pre_scored)

    def generate_risk_geojson(
        self,
        scored: list[dict],
        original: dict,
    ) -> dict:
        """Reintegra los scores de riesgo al GeoJSON original.

        Enriquece cada Feature.properties con:
            score_riesgo, clasificacion, color_leaflet,
            factores_riesgo, recomendaciones_mitigacion,
            razon_descarte, score_source.

        Features sin score reciben clasificacion "DESCONOCIDO" y color "#64748b".

        Args:
            scored:   Salida de RiskAgent.score().
            original: FeatureCollection GeoJSON del fixture.

        Returns:
            Nueva FeatureCollection enriquecida (copia profunda).

        Raises:
            ValueError: Si original no es FeatureCollection.
        """
        if original.get("type") != "FeatureCollection":
            raise ValueError("original debe ser una FeatureCollection GeoJSON.")

        score_map: dict[str, dict] = {
            str(s["id"]): s for s in scored if "id" in s
        }

        enriched = copy.deepcopy(original)
        matched = 0

        for feature in enriched.get("features", []):
            props = feature.setdefault("properties", {})
            fid   = str(props.get("id") or feature.get("id") or "")
            rec   = score_map.get(fid)

            if rec:
                props["score_riesgo"]               = rec.get("score_riesgo")
                props["clasificacion"]               = rec.get("clasificacion")
                props["color_leaflet"]               = rec.get("color_leaflet", "#64748b")
                props["factores_riesgo"]             = rec.get("factores_riesgo", [])
                props["recomendaciones_mitigacion"]  = rec.get("recomendaciones_mitigacion", [])
                props["razon_descarte"]              = rec.get("razon_descarte", "")
                props["score_source"]                = rec.get("score_source", "fallback")
                matched += 1
            else:
                props["score_riesgo"]               = None
                props["clasificacion"]               = "DESCONOCIDO"
                props["color_leaflet"]               = "#64748b"
                props["factores_riesgo"]             = []
                props["recomendaciones_mitigacion"]  = []
                props["razon_descarte"]              = ""
                props["score_source"]                = "missing"
                logger.warning("Feature '%s' sin score de riesgo.", fid)

        logger.info(
            "generate_risk_geojson: %d/%d features enriquecidas.",
            matched,
            len(enriched.get("features", [])),
        )
        return enriched

    # ── Paso 1: pre-scoring algoritmico ─────────────────────────────────────

    def _pre_score(self, features: list[dict]) -> list[dict]:
        """Calcula score y clasificacion algoritmica y los anota en cada feature.

        Los campos _pre_score_riesgo_ y _pre_clasif_ son temporales y se
        usan para construir el prompt de Watsonx.

        Args:
            features: Features normalizadas.

        Returns:
            Copia de las features con _pre_score_riesgo_ y _pre_clasif_ anadidos.
        """
        result = []
        for feat in features:
            f = dict(feat)
            s = _compute_raw_risk(f)
            c = _classify(s)
            f["_pre_score_riesgo_"] = s
            f["_pre_clasif_"]       = c
            result.append(f)
        logger.debug("_pre_score: %d features pre-puntuadas.", len(result))
        return result

    # ── Paso 2: Watsonx ──────────────────────────────────────────────────────

    def _score_with_watsonx(self, pre_scored: list[dict]) -> list[dict]:
        """Envia features a Watsonx y parsea la respuesta con narrativa.

        Args:
            pre_scored: Features con _pre_score_riesgo_ y _pre_clasif_.

        Returns:
            Lista de records de riesgo con narrativa del LLM.

        Raises:
            RuntimeError: Si todos los lotes/reintentos fallan.
        """
        logger.info(
            "_score_with_watsonx: %d features en lotes de %d.",
            len(pre_scored),
            BATCH_SIZE,
        )
        system = _SYSTEM_PROMPT_TEMPLATE.format(few_shot=_FEW_SHOT)
        results: list[dict] = []

        for start in range(0, len(pre_scored), BATCH_SIZE):
            batch = pre_scored[start : start + BATCH_SIZE]
            slim  = _slim_for_risk(batch)
            user_prompt = (
                f"Analiza las {len(slim)} manzanas y confirma/ajusta el score de riesgo.\n"
                "Devuelve SOLO el array JSON:\n\n"
                + json.dumps(slim, ensure_ascii=False, indent=2)
            )
            combined = (
                _GRANITE_SYS_OPEN + "\n" + system + "\n" +
                _GRANITE_USR_OPEN + "\n" + user_prompt + "\n" +
                _GRANITE_RES_OPEN + "\n"
            )
            raw = _call_watsonx_rest(
                combined_input=combined,
                api_key=self._api_key,
                project_id=self._project_id,
                base_url=self._base_url,
            )
            parsed = _parse_risk_response(raw)
            # Enriquecer con color y campos extra desde pre_scored
            id_to_pre = {f["id"]: f for f in batch}
            for rec in parsed:
                pre = id_to_pre.get(rec.get("id"), {})
                rec["color_leaflet"]   = RISK_COLORS.get(rec.get("clasificacion", ""), "#64748b")
                rec["score_source"]    = "watsonx"
                rec["incidencia_raw"]  = pre.get("incidencia_delictiva_snsp_raw")
                rec["tipo_delito"]     = pre.get("tipo_delito_predominante", "N/D")
                rec["iluminacion_raw"] = pre.get("iluminacion_publica_raw")
                rec["accesibilidad_raw"] = pre.get("accesibilidad_logistica_raw")
                rec.setdefault("nombre", pre.get("nombre"))
            results.extend(parsed)

        logger.info("Watsonx: %d scores de riesgo recibidos.", len(results))
        return results

    # ── Paso 3: fallback algoritmico ────────────────────────────────────────

    def _score_fallback(self, pre_scored: list[dict]) -> list[dict]:
        """Clasificacion puramente algoritmica sin narrativa LLM.

        Args:
            pre_scored: Features con _pre_score_riesgo_ y _pre_clasif_.

        Returns:
            Lista de records de riesgo completos con score_source="fallback".
        """
        results = []
        for feat in pre_scored:
            score  = feat["_pre_score_riesgo_"]
            clasif = feat["_pre_clasif_"]
            results.append(_build_fallback_record(feat, score, clasif))
        logger.debug("_score_fallback: %d records generados.", len(results))
        return results


# ---------------------------------------------------------------------------
# Funcion compartida de llamada REST a Watsonx
# ---------------------------------------------------------------------------


def _call_watsonx_rest(
    combined_input: str,
    api_key: str,
    project_id: str,
    base_url: str,
) -> dict:
    """Llama al endpoint REST de Watsonx con retry + backoff exponencial.

    Parametros fijos del modelo:
        max_new_tokens: 800
        temperature   : 0.1
        top_p         : 0.9

    Args:
        combined_input: Prompt completo ya formateado (system+user+assistant).
        api_key:        IAM API key.
        project_id:     Project ID Watsonx.
        base_url:       URL base del servicio.

    Returns:
        Respuesta deserializada de Watsonx.

    Raises:
        EnvironmentError: Si faltan credenciales.
        RuntimeError: Si todos los reintentos fallan.
    """
    if not api_key or not project_id:
        raise EnvironmentError(
            "Credenciales Watsonx no configuradas. "
            "Define WATSONX_API_KEY y WATSONX_PROJECT_ID."
        )

    endpoint = WATSONX_ENDPOINT.format(base_url=base_url)
    iam_token = _get_iam_token(api_key)

    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload: dict[str, Any] = {
        "model_id":   WATSONX_MODEL_ID,
        "project_id": project_id,
        "input":      combined_input,
        "parameters": {
            "max_new_tokens": 800,
            "temperature":    0.1,
            "top_p":          0.9,
            "stop_sequences": [_GRANITE_EOT],
        },
    }

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        wait = BACKOFF_BASE ** (attempt - 1)
        try:
            if attempt > 1:
                logger.debug("_call_watsonx_rest: esperando %.1fs antes del intento %d.", wait, attempt)
                time.sleep(wait)

            with httpx.Client(timeout=60.0) as client:
                resp = client.post(endpoint, headers=headers, json=payload)

            # No reintentar errores 4xx (excepto rate-limit 429)
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()

            resp.raise_for_status()
            logger.info("_call_watsonx_rest: respuesta OK en intento %d.", attempt)
            return resp.json()

        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP %d en intento %d: %s", exc.response.status_code, attempt, exc)
            last_exc = exc
        except httpx.RequestError as exc:
            logger.warning("Error de red en intento %d: %s", attempt, exc)
            last_exc = exc
        except Exception as exc:  # noqa: BLE001
            logger.error("Error inesperado en intento %d: %s", attempt, exc)
            last_exc = exc

    raise RuntimeError(
        f"_call_watsonx_rest: fallaron los {MAX_RETRIES} intentos. "
        f"Ultimo error: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _get_iam_token(api_key: str) -> str:
    """Obtiene un IAM Bearer token de IBM Cloud.

    Args:
        api_key: IAM API key de IBM Cloud.

    Returns:
        Bearer token como string.

    Raises:
        RuntimeError: Si la solicitud de token falla.
    """
    try:
        response = httpx.post(
            IAM_TOKEN_ENDPOINT,
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": api_key,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        response.raise_for_status()
        token = response.json().get("access_token", "")
        if not token:
            raise ValueError("access_token vacio en respuesta IAM.")
        return token
    except Exception as exc:
        raise RuntimeError(f"No se pudo obtener el IAM token: {exc}") from exc


def _parse_risk_response(raw: dict) -> list[dict]:
    """Extrae y valida el array JSON de la respuesta de Watsonx.

    Args:
        raw: Respuesta completa de _call_watsonx_rest.

    Returns:
        Lista de dicts validados con las claves del schema de riesgo.

    Raises:
        ValueError: Si el JSON es invalido o faltan claves obligatorias.
    """
    try:
        text: str = raw["results"][0]["generated_text"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Estructura de respuesta Watsonx inesperada: {exc}") from exc

    json_text = _extract_json_array(text)

    try:
        parsed: list = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Texto generado no es JSON valido: {exc}\nTexto: {text[:400]}"
        ) from exc

    if not isinstance(parsed, list):
        raise ValueError(f"Se esperaba array JSON, se obtuvo: {type(parsed).__name__}")

    required = {"id", "score_riesgo", "clasificacion", "factores_riesgo",
                "recomendaciones_mitigacion", "razon_descarte"}

    for i, rec in enumerate(parsed):
        if not isinstance(rec, dict):
            raise ValueError(f"Elemento [{i}] no es un objeto JSON.")

        missing = required - set(rec.keys())
        if missing:
            raise ValueError(f"Elemento [{i}] le faltan claves: {missing}")

        # Coercion y rangos de score
        try:
            rec["score_riesgo"] = round(
                min(max(float(rec["score_riesgo"]), 0.0), 100.0), 2
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"score_riesgo invalido en elemento [{i}]: {rec.get('score_riesgo')}"
            ) from exc

        # Asegurar clasificacion valida
        clasif = rec.get("clasificacion", "")
        if clasif not in RISK_COLORS:
            rec["clasificacion"] = _classify(rec["score_riesgo"])
            logger.warning(
                "Clasificacion '%s' invalida en [%d] — recalculada como '%s'.",
                clasif, i, rec["clasificacion"],
            )

        # Garantizar listas
        if not isinstance(rec.get("factores_riesgo"), list):
            rec["factores_riesgo"] = []
        if not isinstance(rec.get("recomendaciones_mitigacion"), list):
            rec["recomendaciones_mitigacion"] = []
        if not isinstance(rec.get("razon_descarte"), str):
            rec["razon_descarte"] = ""

    logger.debug("_parse_risk_response: %d records validados.", len(parsed))
    return parsed


def _extract_json_array(text: str) -> str:
    """Extrae el substring de array JSON de un texto con posible ruido.

    Args:
        text: Texto generado por Watsonx.

    Returns:
        Substring que contiene el array JSON.

    Raises:
        ValueError: Si no se encuentran los delimitadores [ y ].
    """
    start = text.find("[")
    end   = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"No se encontro un array JSON en la respuesta: {text[:300]!r}"
        )
    return text[start : end + 1]


# ---------------------------------------------------------------------------
# Wrappers de compatibilidad con el modulo original (Paso 1)
# ---------------------------------------------------------------------------


def compute_risk_score(feature: dict) -> float:
    """Wrapper de compatibilidad. Calcula score de riesgo desde Feature GeoJSON cruda.

    Mantiene compatibilidad con routes/geojson_export.py del Paso 1.

    Args:
        feature: Feature GeoJSON con properties (campos raw).

    Returns:
        Score de riesgo [0-100].
    """
    from data.ingest import _ensure_norm_fields  # noqa: PLC0415

    props = feature.get("properties", {})
    norm  = _ensure_norm_fields(props)
    return _compute_raw_risk(norm)


def classify_risk(risk_score: float) -> str:
    """Wrapper de compatibilidad. Clasifica el score de riesgo.

    Args:
        risk_score: Score de riesgo [0-100].

    Returns:
        "VERDE", "CAUTELA" o "DESCARTE". (Anteriormente "BAJO"/"MEDIO"/"ALTO")
    """
    return _classify(risk_score)


def analyze_risk(features: list[dict]) -> list[dict]:
    """Wrapper de compatibilidad con el codigo del Paso 1.

    Recibe Features GeoJSON crudas y retorna scores de riesgo.

    Args:
        features: Lista de Features GeoJSON del fixture.

    Returns:
        Lista de dicts con id, nombre, risk_score, risk_tier, tipo_delito, delitos_anuales.
    """
    agent = RiskAgent(use_fallback_only=True)
    from data.ingest import _ensure_norm_fields  # noqa: PLC0415

    normalized = [_ensure_norm_fields(f.get("properties", {})) for f in features]
    # Agregar campos de identificacion que vienen en properties
    for norm, feat in zip(normalized, features):
        props = feat.get("properties", {})
        for k in ("id", "nombre", "tipo_delito_predominante"):
            if k not in norm:
                norm[k] = props.get(k)

    results = agent.score(normalized)

    # Renombrear para compat
    output = []
    for r in results:
        output.append({
            "id":              r.get("id"),
            "nombre":          r.get("nombre"),
            "risk_score":      r.get("score_riesgo"),
            "risk_tier":       r.get("clasificacion"),
            "tipo_delito":     r.get("tipo_delito", "N/D"),
            "delitos_anuales": r.get("incidencia_raw"),
        })
    return output


def generate_risk_narrative(high_risk_features: list[dict], watsonx_client=None) -> str:
    """Wrapper de compatibilidad. Genera narrativa de riesgo en modo demo.

    Args:
        high_risk_features: Features con mayor riesgo.
        watsonx_client:     Ignorado en demo (futuro uso en produccion).

    Returns:
        Parrafo ejecutivo de texto.
    """
    if not high_risk_features:
        return "No se identificaron zonas de alto riesgo en el area analizada."
    names = [f.get("nombre", f.get("id", "?")) for f in high_risk_features[:3]]
    return (
        f"Las manzanas {', '.join(names)} presentan niveles de riesgo elevados "
        "principalmente por alta incidencia delictiva y deficit de iluminacion publica. "
        "Se recomienda evaluar medidas de mitigacion antes de cualquier inversion."
    )
