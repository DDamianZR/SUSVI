"""
URBANIA - Agente de Demanda (IBM Watsonx AI)
============================================

Responsabilidades
-----------------
- Calcular el score_demanda [0-100] de cada manzana segun el sector
  de negocio usando IBM Watsonx AI (Granite 13B Instruct v2).
- Aplicar pesos diferenciados por sector (telecomunicaciones, seguridad,
  inmobiliario) tanto en el prompt como en el fallback algoritmico.
- Reintegrar los scores al GeoJSON original para su consumo por Leaflet.

Modo de operacion
-----------------
- Produccion: llama a Watsonx REST API con retry + backoff exponencial.
- Fallback / demo: promedio ponderado puro si Watsonx no esta disponible.

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

SUPPORTED_SECTORS: frozenset[str] = frozenset(
    {"telecomunicaciones", "seguridad", "inmobiliario"}
)

MAX_RETRIES: int = 3
BACKOFF_BASE: float = 2.0
BATCH_SIZE: int = 25

# Marcadores de formato para el prompt Granite 13B Instruct
_GRANITE_SYS_OPEN  = "<|system|>"
_GRANITE_SYS_CLOSE = "<|end_of_text|>"
_GRANITE_USR_OPEN  = "<|user|>"
_GRANITE_RES_OPEN  = "<|assistant|>"

# ---------------------------------------------------------------------------
# Pesos por sector
# ---------------------------------------------------------------------------

SECTOR_WEIGHTS: dict[str, dict[str, float]] = {
    "telecomunicaciones": {
        "densidad_poblacional_norm":      0.30,
        "actividad_economica_denue_norm": 0.25,
        "luminosidad_viirs_norm":         0.20,
        "acceso_gtfs_norm":               0.15,
        # ingreso_estimado -> proxy: (actividad * 0.7 + luminosidad * 0.3) * 0.10
        "__ingreso_proxy__":              0.10,
    },
    "seguridad": {
        "luminosidad_viirs_norm":         0.35,   # actividad_nocturna proxy
        "acceso_gtfs_norm":               0.30,   # flujos_peatonales proxy
        "densidad_poblacional_norm":      0.20,
        "actividad_economica_denue_norm": 0.15,   # comercio_formal proxy
    },
    "inmobiliario": {
        "luminosidad_viirs_norm":         0.30,   # expansion_urbana proxy
        "acceso_gtfs_norm":               0.25,
        "densidad_poblacional_norm":      0.25,
        "actividad_economica_denue_norm": 0.20,
    },
}

# ---------------------------------------------------------------------------
# Few-shot examples para Watsonx
# ---------------------------------------------------------------------------

_FEW_SHOT_EXAMPLES: str = json.dumps(
    [
        {
            "id": "MZ-001",
            "score_demanda": 87.4,
            "justificacion_top3": [
                "Alta densidad poblacional (22000 hab/km2) garantiza masa critica de usuarios.",
                "385 establecimientos DENUE reflejan ecosistema comercial consolidado.",
                "Luminosidad VIIRS 240 indica actividad nocturna intensa.",
            ],
        },
        {
            "id": "MZ-018",
            "score_demanda": 12.1,
            "justificacion_top3": [
                "Luminosidad VIIRS 60 evidencia baja actividad nocturna.",
                "Solo 112 establecimientos DENUE, mercado informal o deprimido.",
                "Sin cobertura GTFS: accesibilidad logistica muy limitada.",
            ],
        },
    ],
    ensure_ascii=False,
    indent=2,
)

# ---------------------------------------------------------------------------
# Criterios por sector para el prompt
# ---------------------------------------------------------------------------

_CRITERIA_BY_SECTOR: dict[str, str] = {
    "telecomunicaciones": (
        "- Densidad poblacional (30%): mas habitantes = mayor base de suscriptores.\n"
        "- Actividad economica DENUE (25%): establecimientos formales demandan conectividad.\n"
        "- Luminosidad VIIRS (20%): proxy de actividad nocturna e infraestructura.\n"
        "- Acceso GTFS (15%): corredores de alta demanda de conectividad.\n"
        "- Ingreso estimado / proxy (10%): combinacion actividad + luminosidad."
    ),
    "seguridad": (
        "- Actividad nocturna / luminosidad VIIRS (35%): zonas oscuras necesitan seguridad.\n"
        "- Flujos peatonales / acceso GTFS (30%): trafico alto = mayor demanda de vigilancia.\n"
        "- Densidad poblacional (20%): mas habitantes = mas clientes potenciales.\n"
        "- Comercio formal / DENUE (15%): negocios con necesidad de proteccion patrimonial."
    ),
    "inmobiliario": (
        "- Expansion urbana / luminosidad VIIRS (30%): zonas iluminadas muestran valorizacion.\n"
        "- Acceso GTFS (25%): conectividad de transporte = plusvalia inmobiliaria.\n"
        "- Densidad poblacional (25%): demanda habitacional y comercial consolidada.\n"
        "- Actividad economica DENUE (20%): ecosistema de negocios atrae inversion."
    ),
}

# Labels legibles de campos
_FIELD_LABELS: dict[str, str] = {
    "densidad_poblacional_norm":      "Densidad poblacional",
    "actividad_economica_denue_norm": "Actividad economica DENUE",
    "luminosidad_viirs_norm":         "Luminosidad nocturna VIIRS",
    "acceso_gtfs_norm":               "Acceso a transporte publico GTFS",
    "iluminacion_publica_norm":       "Iluminacion publica",
    "accesibilidad_logistica_norm":   "Accesibilidad logistica",
    "__ingreso_proxy__":              "Ingreso estimado (proxy)",
}


def _field_label(field: str) -> str:
    """Retorna etiqueta legible de un campo normalizado."""
    return _FIELD_LABELS.get(
        field,
        field.replace("_norm", "").replace("_", " ").capitalize(),
    )


def _tier_label(score: float | None) -> str:
    """Convierte score numerico en categoria de demanda."""
    if score is None:
        return "DESCONOCIDO"
    if score >= 70:
        return "ALTA"
    if score >= 45:
        return "MEDIA"
    return "BAJA"


def _slim_features(features: list[dict], sector: str) -> list[dict]:
    """Proyecta solo campos relevantes para reducir tokens enviados a Watsonx.

    Args:
        features: Lista de features normalizadas completas.
        sector:   Sector activo (para filtrar pesos).

    Returns:
        Lista de dicts con id, nombre, lat, lng y campos _norm relevantes.
    """
    relevant = set(SECTOR_WEIGHTS[sector].keys()) - {"__ingreso_proxy__"}
    base_fields = {"id", "nombre", "lat", "lng"}
    slim = []
    for feat in features:
        record: dict[str, Any] = {k: feat[k] for k in base_fields if k in feat}
        for field in relevant:
            if field in feat:
                record[field] = round(float(feat[field]), 2)
        slim.append(record)
    return slim


# ---------------------------------------------------------------------------
# Clase principal: DemandAgent
# ---------------------------------------------------------------------------


class DemandAgent:
    """Agente de Demanda URBANIA impulsado por IBM Watsonx AI (Granite 13B).

    Calcula el score_demanda [0-100] de cada manzana normalizada. Si Watsonx
    no esta disponible, aplica fallback de promedio ponderado.

    Args:
        sector:            Sector de negocio. Uno de SUPPORTED_SECTORS.
        use_fallback_only: Si True, omite Watsonx (demo/testing).

    Raises:
        ValueError: Si sector no esta en SUPPORTED_SECTORS.

    Example::

        agent = DemandAgent(sector="inmobiliario")
        scored = agent.score(normalized_features)
        enriched_geojson = agent.to_geojson(scored, original_geojson)
    """

    def __init__(self, sector: str, use_fallback_only: bool = False) -> None:
        if sector not in SUPPORTED_SECTORS:
            raise ValueError(
                f"Sector '{sector}' no soportado. "
                f"Opciones validas: {sorted(SUPPORTED_SECTORS)}"
            )
        self.sector: str = sector
        self.use_fallback_only: bool = use_fallback_only
        self.weights: dict[str, float] = SECTOR_WEIGHTS[sector]

        self._api_key: str = os.environ.get("WATSONX_API_KEY", "")
        self._project_id: str = os.environ.get("WATSONX_PROJECT_ID", "")
        self._base_url: str = os.environ.get(
            "WATSONX_URL", "https://us-south.ml.cloud.ibm.com"
        ).rstrip("/")

        logger.info(
            "DemandAgent inicializado — sector='%s'  fallback_only=%s  watsonx_configured=%s",
            sector,
            use_fallback_only,
            bool(self._api_key and self._project_id),
        )

    # ── API publica ─────────────────────────────────────────────────────────

    def score(self, features: list[dict], sector: str | None = None) -> list[dict]:
        """Calcula el score de demanda para una lista de manzanas normalizadas.

        Intenta usar Watsonx AI. Si falla, aplica fallback algoritmico.

        Args:
            features: Dicts normalizados de ingest.normalize_features.
                      Deben contener campos <campo>_norm de SECTOR_WEIGHTS.
            sector:   Sobreescribe el sector del agente si se proporciona.

        Returns:
            Lista de dicts por manzana con:
            - id (str)
            - nombre (str)
            - score_demanda (float, 0-100)
            - demand_tier ("ALTA" | "MEDIA" | "BAJA")
            - justificacion_top3 (list[str], 3 elementos)
            - score_source ("watsonx" | "fallback")

        Raises:
            ValueError: Si features esta vacia o sector es invalido.
        """
        if not features:
            raise ValueError("La lista de features no puede estar vacia.")

        effective_sector = sector if sector is not None else self.sector
        if effective_sector not in SUPPORTED_SECTORS:
            raise ValueError(
                f"Sector '{effective_sector}' no soportado. "
                f"Opciones validas: {sorted(SUPPORTED_SECTORS)}"
            )

        logger.info(
            "DemandAgent.score — %d manzanas  sector='%s'",
            len(features),
            effective_sector,
        )

        if not self.use_fallback_only and self._api_key and self._project_id:
            try:
                return self._score_with_watsonx(features, effective_sector)
            except EnvironmentError:
                logger.warning("Credenciales Watsonx invalidas — usando fallback.")
            except RuntimeError as exc:
                logger.warning("Watsonx fallo tras reintentos (%s) — usando fallback.", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Error inesperado en Watsonx (%s: %s) — usando fallback.",
                    type(exc).__name__,
                    exc,
                )

        logger.info("Usando fallback algoritmico para sector='%s'.", effective_sector)
        return self._score_fallback(features, effective_sector)

    def to_geojson(
        self,
        scored_features: list[dict],
        original_geojson: dict,
    ) -> dict:
        """Reintegra scores de demanda al GeoJSON original (copia profunda).

        Features sin score reciben score_demanda=None y demand_tier=DESCONOCIDO.

        Args:
            scored_features: Salida de DemandAgent.score().
            original_geojson: FeatureCollection GeoJSON cruda del fixture.

        Returns:
            Nueva FeatureCollection con score_demanda, demand_tier,
            justificacion_top3 y score_source en cada Feature.properties.

        Raises:
            ValueError: Si original_geojson no es FeatureCollection.
        """
        if original_geojson.get("type") != "FeatureCollection":
            raise ValueError(
                "original_geojson debe ser una FeatureCollection GeoJSON."
            )

        score_map: dict[str, dict] = {
            str(s["id"]): s for s in scored_features if "id" in s
        }

        enriched = copy.deepcopy(original_geojson)
        matched = 0

        for feature in enriched.get("features", []):
            props = feature.setdefault("properties", {})
            fid = str(props.get("id") or feature.get("id") or "")
            scored = score_map.get(fid)

            if scored:
                props["score_demanda"]      = scored.get("score_demanda")
                props["justificacion_top3"] = scored.get("justificacion_top3", [])
                props["score_source"]       = scored.get("score_source", "fallback")
                props["demand_tier"]        = _tier_label(scored.get("score_demanda"))
                matched += 1
            else:
                props["score_demanda"]      = None
                props["justificacion_top3"] = []
                props["score_source"]       = "missing"
                props["demand_tier"]        = "DESCONOCIDO"
                logger.warning("Feature '%s' sin score asignado.", fid)

        logger.info(
            "to_geojson: %d/%d features enriquecidas con score_demanda.",
            matched,
            len(enriched.get("features", [])),
        )
        return enriched

    # ── Logica interna – Watsonx ────────────────────────────────────────────

    def _score_with_watsonx(self, features: list[dict], sector: str) -> list[dict]:
        """Llama a Watsonx AI en lotes y parsea respuesta JSON.

        Args:
            features: Features normalizadas.
            sector:   Sector activo.

        Returns:
            Lista de dicts con score_demanda y justificacion_top3.

        Raises:
            RuntimeError: Si todos los intentos de todos los lotes fallan.
        """
        logger.info(
            "_score_with_watsonx: %d features en lotes de %d, sector=%s.",
            len(features),
            BATCH_SIZE,
            sector,
        )
        system_prompt = self._build_system_prompt(sector)
        results: list[dict] = []

        for start in range(0, len(features), BATCH_SIZE):
            batch = features[start : start + BATCH_SIZE]
            logger.debug("Lote [%d:%d] enviado a Watsonx.", start, start + len(batch) - 1)
            user_prompt = self._build_user_prompt(batch, sector)
            raw_response = call_watsonx(
                prompt=user_prompt,
                system=system_prompt,
                api_key=self._api_key,
                project_id=self._project_id,
                base_url=self._base_url,
            )
            parsed = _parse_watsonx_response(raw_response)
            for record in parsed:
                record["score_source"] = "watsonx"
            results.extend(parsed)

        logger.info("Watsonx: %d scores recibidos.", len(results))
        return results

    def _build_system_prompt(self, sector: str) -> str:
        """Construye system prompt con criterios sectoriales y few-shot examples."""
        criteria = _CRITERIA_BY_SECTOR.get(sector, "Criterios no definidos.")
        return "\n".join([
            "Eres URBANIA-DemandAgent, experto en inteligencia territorial.",
            f'Tu tarea: calcular score_demanda (0-100) por manzana para el sector "{sector}".',
            "",
            "REGLAS ESTRICTAS:",
            "1. Responde UNICAMENTE con array JSON valido. SIN texto fuera del JSON.",
            "2. Cada objeto del array debe tener exactamente las claves:",
            '   - "id"                : string identificador de manzana',
            '   - "score_demanda"     : float con 1 decimal, rango [0.0, 100.0]',
            '   - "justificacion_top3": array de exactamente 3 strings (max 120 chars c/u)',
            "3. Orden del array debe coincidir con el orden de entrada.",
            "4. Campos nulos o faltantes -> asumir valor neutro (50).",
            "",
            f'CRITERIOS PARA SECTOR "{sector}":',
            criteria,
            "",
            "EJEMPLO DE OUTPUT ESPERADO (2 manzanas de referencia):",
            _FEW_SHOT_EXAMPLES,
        ])

    def _build_user_prompt(self, batch: list[dict], sector: str) -> str:
        """Construye user prompt con datos del lote de features."""
        slim = _slim_features(batch, sector)
        return "\n".join([
            f'Analiza las {len(slim)} manzanas para el sector "{sector}".',
            "Devuelve SOLO el array JSON:",
            "",
            json.dumps(slim, ensure_ascii=False, indent=2),
        ])

    # ── Fallback algoritmico ─────────────────────────────────────────────────

    def _score_fallback(self, features: list[dict], sector: str) -> list[dict]:
        """Promedio ponderado puro sin LLM.

        El campo especial __ingreso_proxy__ se calcula como:
        (actividad_economica_denue_norm * 0.7 + luminosidad_viirs_norm * 0.3).

        Args:
            features: Features normalizadas.
            sector:   Sector activo.

        Returns:
            Lista de dicts con score_demanda, demand_tier,
            justificacion_top3 y score_source="fallback".
        """
        weights = SECTOR_WEIGHTS[sector]
        results: list[dict] = []

        for feat in features:
            score = 0.0
            contributions: list[tuple[float, str]] = []

            for field, weight in weights.items():
                if field == "__ingreso_proxy__":
                    proxy_val = (
                        float(feat.get("actividad_economica_denue_norm", 50.0)) * 0.7
                        + float(feat.get("luminosidad_viirs_norm", 50.0)) * 0.3
                    )
                    contribution = proxy_val * weight
                    label = _field_label("__ingreso_proxy__")
                else:
                    raw_val = float(feat.get(field, 50.0))
                    contribution = raw_val * weight
                    label = _field_label(field)

                score += contribution
                contributions.append((contribution, label))

            score = round(min(max(score, 0.0), 100.0), 2)
            top3 = sorted(contributions, key=lambda x: x[0], reverse=True)[:3]
            justificacion = [
                f"{label}: contribucion {val:.1f} pts al score de demanda."
                for val, label in top3
            ]

            results.append({
                "id":                 feat.get("id"),
                "nombre":             feat.get("nombre"),
                "score_demanda":      score,
                "demand_tier":        _tier_label(score),
                "justificacion_top3": justificacion,
                "score_source":       "fallback",
            })

        logger.debug("_score_fallback: %d scores (sector='%s').", len(results), sector)
        return results


# ---------------------------------------------------------------------------
# Funcion publica: call_watsonx
# ---------------------------------------------------------------------------


def call_watsonx(
    prompt: str,
    system: str,
    api_key: str | None = None,
    project_id: str | None = None,
    base_url: str | None = None,
) -> dict:
    """Llama al endpoint REST de IBM Watsonx AI con retry + backoff exponencial.

    Endpoint: POST /ml/v1/text/generation?version=2023-05-29

    Parametros del modelo fijos:
        max_new_tokens : 800
        temperature    : 0.1  (respuestas deterministas / estructuradas)
        top_p          : 0.9

    Estrategia de retry (3 intentos, backoff exponencial de base 2s):
        - HTTP 429 y 5xx activan el retry.
        - HTTP 4xx (salvo 429) lanzan excepcion inmediata.
        - Errores de red/timeout activan el retry.

    Args:
        prompt:     Texto del usuario con features a analizar.
        system:     System prompt con criterios y few-shot examples.
        api_key:    IAM API key IBM Cloud. None = leer WATSONX_API_KEY.
        project_id: Project ID. None = leer WATSONX_PROJECT_ID.
        base_url:   URL base. None = leer WATSONX_URL.

    Returns:
        Diccionario con la respuesta deserializada de Watsonx.

    Raises:
        EnvironmentError: Si faltan WATSONX_API_KEY o WATSONX_PROJECT_ID.
        RuntimeError: Si todos los intentos fallan.
    """
    resolved_key = api_key or os.environ.get("WATSONX_API_KEY", "")
    resolved_pid = project_id or os.environ.get("WATSONX_PROJECT_ID", "")
    resolved_url = (
        base_url
        or os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    ).rstrip("/")

    if not resolved_key or not resolved_pid:
        raise EnvironmentError(
            "Credenciales Watsonx no configuradas. "
            "Define WATSONX_API_KEY y WATSONX_PROJECT_ID."
        )

    endpoint = WATSONX_ENDPOINT.format(base_url=resolved_url)
    iam_token = _get_iam_token(resolved_key)

    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Formato de input para Granite 13B: system + user + assistant marker
    combined_input = (
        _GRANITE_SYS_OPEN  + "\n" + system + "\n" +
        _GRANITE_USR_OPEN  + "\n" + prompt + "\n" +
        _GRANITE_RES_OPEN  + "\n"
    )

    payload: dict[str, Any] = {
        "model_id": WATSONX_MODEL_ID,
        "project_id": resolved_pid,
        "input": combined_input,
        "parameters": {
            "max_new_tokens": 800,
            "temperature":    0.1,
            "top_p":          0.9,
            "stop_sequences": [_GRANITE_SYS_CLOSE],
        },
    }

    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        wait_time = BACKOFF_BASE ** (attempt - 1)
        try:
            logger.debug(
                "call_watsonx: intento %d/%d (espera previas: %.1fs)",
                attempt,
                MAX_RETRIES,
                0.0 if attempt == 1 else wait_time,
            )
            if attempt > 1:
                time.sleep(wait_time)

            with httpx.Client(timeout=60.0) as client:
                response = client.post(endpoint, headers=headers, json=payload)

            # Errores 4xx (excepto 429) no deben reintentarse
            if response.status_code not in (429,) and 400 <= response.status_code < 500:
                response.raise_for_status()

            response.raise_for_status()
            result: dict = response.json()
            logger.info("call_watsonx: respuesta OK en intento %d.", attempt)
            return result

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "call_watsonx: HTTP %d en intento %d — %s",
                exc.response.status_code,
                attempt,
                exc,
            )
            last_exc = exc
        except httpx.RequestError as exc:
            logger.warning(
                "call_watsonx: error de red en intento %d — %s", attempt, exc
            )
            last_exc = exc
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "call_watsonx: error inesperado en intento %d — %s", attempt, exc
            )
            last_exc = exc

    raise RuntimeError(
        f"call_watsonx: fallaron los {MAX_RETRIES} intentos. "
        f"Ultimo error: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _get_iam_token(api_key: str) -> str:
    """Obtiene un IAM Bearer token de IBM Cloud usando la API key.

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
        token_data = response.json()
        token = token_data.get("access_token", "")
        if not token:
            raise ValueError("access_token vacio en respuesta IAM.")
        logger.debug("_get_iam_token: token obtenido exitosamente.")
        return token
    except Exception as exc:
        raise RuntimeError(f"No se pudo obtener el IAM token: {exc}") from exc


def _parse_watsonx_response(raw_response: dict) -> list[dict]:
    """Extrae y valida el JSON generado por Watsonx de la respuesta REST.

    El texto generado debe ser un array JSON. Esta funcion lo extrae
    de results[0].generated_text y lo parsea.

    Args:
        raw_response: Respuesta completa deserializada de call_watsonx.

    Returns:
        Lista de dicts con id, score_demanda y justificacion_top3.

    Raises:
        ValueError: Si el texto generado no es un JSON valido o falta
                    alguna clave obligatoria en los records.
    """
    try:
        generated_text: str = raw_response["results"][0]["generated_text"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            f"Estructura de respuesta Watsonx inesperada: {exc}. "
            f"Respuesta: {raw_response}"
        ) from exc

    # Intentar extraer el JSON aunque haya texto adicional
    json_text = _extract_json_array(generated_text)

    try:
        parsed: list = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"El texto generado por Watsonx no es JSON valido: {exc}\n"
            f"Texto: {generated_text[:500]}"
        ) from exc

    if not isinstance(parsed, list):
        raise ValueError(
            f"Se esperaba un array JSON, se obtuvo: {type(parsed).__name__}"
        )

    # Validar campos obligatorios en cada record
    required_keys = {"id", "score_demanda", "justificacion_top3"}
    for i, record in enumerate(parsed):
        if not isinstance(record, dict):
            raise ValueError(f"El elemento [{i}] del array no es un objeto JSON.")
        missing = required_keys - set(record.keys())
        if missing:
            raise ValueError(
                f"Elemento [{i}] le faltan las claves: {missing}. "
                f"Record: {record}"
            )
        # Coercion y rangos
        try:
            record["score_demanda"] = round(
                min(max(float(record["score_demanda"]), 0.0), 100.0), 2
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"score_demanda invalido en elemento [{i}]: {record.get('score_demanda')}"
            ) from exc

        if not isinstance(record["justificacion_top3"], list):
            raise ValueError(
                f"justificacion_top3 en elemento [{i}] debe ser una lista."
            )
        # Asegurar exactamente 3 justificaciones
        while len(record["justificacion_top3"]) < 3:
            record["justificacion_top3"].append("Sin informacion adicional.")
        record["justificacion_top3"] = record["justificacion_top3"][:3]

    logger.debug("_parse_watsonx_response: %d records validados.", len(parsed))
    return parsed


def _extract_json_array(text: str) -> str:
    """Extrae el substring de array JSON de un texto que puede tener prefijos.

    Busca el primer '[' y el ultimo ']' para extraer el array,
    ignorando texto introductorio o de cierre que el modelo pudiera anadir.

    Args:
        text: Texto generado por Watsonx.

    Returns:
        Substring que contiene solo el array JSON.

    Raises:
        ValueError: Si no se encuentran los delimitadores '[' y ']'.
    """
    start = text.find("[")
    end   = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"No se encontro un array JSON en el texto generado: {text[:300]!r}"
        )
    return text[start : end + 1]


# ---------------------------------------------------------------------------
# Compatibilidad con el modulo original (funciones standalone)
# ---------------------------------------------------------------------------

def compute_demand_score(feature: dict) -> float:
    """Wrapper de compatibilidad. Calcula score de demanda para inmobiliario.

    Mantiene compatibilidad con el codigo que importa esta funcion directamente
    desde el modulo (ej. routes/geojson_export.py).

    Args:
        feature: Feature GeoJSON con properties con campos _norm o raw.

    Returns:
        Score de demanda [0-100] usando sector "inmobiliario" por defecto.
    """
    agent = DemandAgent(sector="inmobiliario", use_fallback_only=True)
    props = feature.get("properties", {})

    # Si los campos _norm no estan, calcular desde raw con rangos fijos
    normalized_feat = _ensure_norm_fields(props)
    results = agent._score_fallback([normalized_feat], "inmobiliario")
    return results[0]["score_demanda"] if results else 0.0


def analyze_demand(features: list[dict]) -> list[dict]:
    """Wrapper de compatibilidad con el codigo original del paso 1.

    Recibe Features GeoJSON (no normalizadas) y calcula scores usando
    el DemandAgent en modo fallback con sector "inmobiliario".

    Args:
        features: Lista de Features GeoJSON crudas.

    Returns:
        Lista de dicts con id, nombre, demand_score y demand_tier.
    """
    agent = DemandAgent(sector="inmobiliario", use_fallback_only=True)
    normalized = [_ensure_norm_fields(f.get("properties", {})) for f in features]
    results = agent._score_fallback(normalized, "inmobiliario")
    # Renombrear score_demanda -> demand_score para compat
    for r in results:
        r["demand_score"] = r.pop("score_demanda", 0.0)
        r["demand_tier"]  = _tier_label(r.get("demand_score"))
    return results


def generate_demand_narrative(top_features: list[dict], watsonx_client=None) -> str:
    """Wrapper de compatibilidad. Genera narrativa de demanda en modo demo."""
    if not top_features:
        return "No se identificaron zonas de alta demanda en la zona analizada."
    names = [f.get("nombre", f.get("id", "?")) for f in top_features[:3]]
    return (
        f"Las manzanas con mayor potencial de demanda son: {', '.join(names)}. "
        "Presentan alta densidad poblacional, actividad economica DENUE robusta "
        "y buena conectividad GTFS, posicionandolas como zonas prioritarias."
    )


def _ensure_norm_fields(props: dict) -> dict:
    """Garantiza que un dict de properties contenga campos _norm.

    Si los campos _norm no existen, los calcula desde valores raw
    con rangos fijos del fixture (min-max globales aproximados).

    Args:
        props: dict de Feature.properties (raw o ya normalizado).

    Returns:
        Dict con campos _norm calculados.
    """
    RANGES = {
        "densidad_poblacional":      (500,   25_000),
        "actividad_economica_denue": (0,     400),
        "luminosidad_viirs":         (0,     255),
        "acceso_gtfs":               (0,     1),
        "incidencia_delictiva_snsp": (0,     500),
        "iluminacion_publica":       (0,     100),
        "accesibilidad_logistica":   (0,     100),
    }

    result = dict(props)

    for field, (vmin, vmax) in RANGES.items():
        norm_key = f"{field}_norm"
        if norm_key not in result:
            if field == "acceso_gtfs":
                raw = 1.0 if result.get(field, False) else 0.0
            else:
                raw = float(result.get(field, (vmin + vmax) / 2))

            if vmax == vmin:
                norm = 50.0
            else:
                norm = (raw - vmin) / (vmax - vmin) * 100.0
                norm = max(0.0, min(100.0, norm))
            result[norm_key] = round(norm, 4)

    return result
