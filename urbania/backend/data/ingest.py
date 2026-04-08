"""
URBANIA – Módulo M1: Ingesta de Datos Territoriales
=====================================================

Responsabilidades
-----------------
1. Cargar y validar el fixture GeoJSON (mock o producción).
2. Normalizar cada Feature al espacio numérico [0-100] homogéneo
   que consumen los tres agentes Watsonx (Demanda, Riesgo, Negocios).
3. Detectar el modo de ejecución (demo vs producción).
4. Orquestar el pipeline completo de ingesta para una zona y sector.

Dependencias permitidas: geopandas, shapely, numpy, json, os, logging.
Sin llamadas a APIs externas en esta capa.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import shape, mapping, Polygon

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de validación
# ---------------------------------------------------------------------------

#: Campos obligatorios que debe tener cada Feature.properties
REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "nombre",
    "lat",
    "lng",
    "densidad_poblacional",
    "actividad_economica_denue",
    "luminosidad_viirs",
    "acceso_gtfs",
    "incidencia_delictiva_snsp",
    "tipo_delito_predominante",
    "iluminacion_publica",
    "accesibilidad_logistica",
)

#: Campos numéricos que serán normalizados (min-max sobre el dataset completo)
NUMERIC_FIELDS: tuple[str, ...] = (
    "densidad_poblacional",
    "actividad_economica_denue",
    "luminosidad_viirs",
    "incidencia_delictiva_snsp",
    "iluminacion_publica",
    "accesibilidad_logistica",
)

#: Campos que se normalizan de forma *invertida*
#: (valor alto → riesgo alto → score_normalizado alto)
INVERTED_FIELDS: frozenset[str] = frozenset({"incidencia_delictiva_snsp"})


# ---------------------------------------------------------------------------
# 1. Carga y validación del fixture
# ---------------------------------------------------------------------------


def load_mock_fixture(path: str) -> dict:
    """Carga el fixture GeoJSON desde disco y valida su estructura mínima.

    Validaciones realizadas:
    - El archivo existe y es JSON válido.
    - El objeto raíz es un GeoJSON ``FeatureCollection``.
    - Contiene al menos una Feature.
    - Cada Feature tiene ``geometry`` (tipo ``Polygon``) y ``properties``.
    - Cada Feature.properties contiene todos los campos en ``REQUIRED_FIELDS``.
    - Los valores numéricos son efectivamente numéricos (int o float).
    - ``acceso_gtfs`` es booleano.

    Args:
        path: Ruta al archivo ``mock_fixture.json`` (absoluta o relativa al CWD).

    Returns:
        Diccionario Python que representa la ``FeatureCollection`` completa.

    Raises:
        FileNotFoundError: Si el archivo no existe en la ruta indicada.
        ValueError: Si el JSON no cumple las validaciones de estructura o tipos.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Fixture no encontrado: {resolved}")

    with open(resolved, encoding="utf-8") as fh:
        try:
            geojson: dict = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"El archivo no es JSON válido: {exc}") from exc

    # ── Validar tipo raíz ──────────────────────────────────────────────────
    if geojson.get("type") != "FeatureCollection":
        raise ValueError(
            f"Se esperaba type='FeatureCollection', se obtuvo: {geojson.get('type')!r}"
        )

    features: list[dict] = geojson.get("features", [])
    if not features:
        raise ValueError("La FeatureCollection no contiene ninguna Feature.")

    # ── Validar cada Feature ───────────────────────────────────────────────
    for idx, feat in enumerate(features):
        _validate_feature(feat, idx)

    logger.info(
        "load_mock_fixture: %d features cargadas desde '%s'",
        len(features),
        resolved.name,
    )
    return geojson


def _validate_feature(feature: dict, idx: int) -> None:
    """Valida la estructura interna de una sola Feature GeoJSON.

    Args:
        feature: Objeto Feature GeoJSON.
        idx: Índice de la Feature en la lista (para mensajes de error).

    Raises:
        ValueError: Si la Feature no cumple las reglas de validación.
    """
    ref = f"Feature[{idx}] id={feature.get('id', '?')!r}"

    if feature.get("type") != "Feature":
        raise ValueError(f"{ref}: type debe ser 'Feature'.")

    geom = feature.get("geometry")
    if geom is None:
        raise ValueError(f"{ref}: geometry es None.")
    if geom.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError(
            f"{ref}: geometry.type debe ser Polygon o MultiPolygon, "
            f"se obtuvo {geom.get('type')!r}."
        )

    props: dict = feature.get("properties") or {}

    # ── Campos obligatorios presentes ─────────────────────────────────────
    missing = [f for f in REQUIRED_FIELDS if f not in props]
    if missing:
        raise ValueError(f"{ref}: faltan campos obligatorios: {missing}")

    # ── Tipos de campos numéricos ──────────────────────────────────────────
    for field in NUMERIC_FIELDS:
        val = props[field]
        if not isinstance(val, (int, float)):
            raise ValueError(
                f"{ref}: '{field}' debe ser numérico, se obtuvo {type(val).__name__!r}."
            )

    # ── acceso_gtfs boolean ────────────────────────────────────────────────
    if not isinstance(props["acceso_gtfs"], bool):
        raise ValueError(
            f"{ref}: 'acceso_gtfs' debe ser booleano, "
            f"se obtuvo {type(props['acceso_gtfs']).__name__!r}."
        )


# ---------------------------------------------------------------------------
# 2. Normalización de Features
# ---------------------------------------------------------------------------


def normalize_features(geojson: dict) -> list[dict]:
    """Transforma cada Feature GeoJSON en un dict normalizado para los agentes.

    Estrategia de normalización
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Se aplica **min-max global** sobre el dataset completo (no por feature),
    lo que garantiza que los scores sean comparables entre manzanas.

    Fórmula estándar (campo ``C``):

    .. code-block:: text

        C_norm = (C - C_min) / (C_max - C_min) * 100

    Campos invertidos (``INVERTED_FIELDS``, e.g. ``incidencia_delictiva_snsp``):

    .. code-block:: text

        C_norm_inv = (1 - (C - C_min) / (C_max - C_min)) * 100

    La geometría GeoJSON original se conserva intacta.
    ``acceso_gtfs`` (booleano) se convierte a 0.0 / 100.0.

    Args:
        geojson: ``FeatureCollection`` validada (salida de ``load_mock_fixture``).

    Returns:
        Lista de dicts normalizados, uno por Feature, con las claves:

        - ``id``, ``nombre``, ``lat``, ``lng``
        - ``geometry`` (GeoJSON Polygon original)
        - ``acceso_gtfs_raw`` (bool original)
        - ``acceso_gtfs_norm`` (0.0 ó 100.0)
        - ``tipo_delito_predominante`` (string sin cambios)
        - ``<field>_raw`` para cada campo numérico
        - ``<field>_norm`` para cada campo numérico (escala 0-100)

    Raises:
        ValueError: Si ``geojson`` no tiene la clave ``features``.
    """
    features: list[dict] = geojson.get("features")
    if features is None:
        raise ValueError("El objeto GeoJSON no contiene la clave 'features'.")

    props_list: list[dict] = [f["properties"] for f in features]

    # ── Calcular estadísticas globales (min/max) por campo numérico ─────────
    stats: dict[str, tuple[float, float]] = _compute_stats(props_list)

    normalized: list[dict] = []
    for feat in features:
        props = feat["properties"]

        record: dict[str, Any] = {
            # Identificadores
            "id":     props["id"],
            "nombre": props["nombre"],
            "lat":    props["lat"],
            "lng":    props["lng"],
            # Geometría original preservada
            "geometry": feat["geometry"],
            # Campo categórico sin transformar
            "tipo_delito_predominante": props.get("tipo_delito_predominante", ""),
            # Boolean → numérico
            "acceso_gtfs_raw":  props["acceso_gtfs"],
            "acceso_gtfs_norm": 100.0 if props["acceso_gtfs"] else 0.0,
        }

        # ── Normalizar campos numéricos ─────────────────────────────────────
        for field in NUMERIC_FIELDS:
            raw_val: float = float(props[field])
            mn, mx = stats[field]
            norm = _minmax_norm(raw_val, mn, mx, invert=field in INVERTED_FIELDS)

            record[f"{field}_raw"]  = raw_val
            record[f"{field}_norm"] = round(norm, 4)

        normalized.append(record)

    logger.info("normalize_features: %d features normalizadas.", len(normalized))
    return normalized


def _compute_stats(props_list: list[dict]) -> dict[str, tuple[float, float]]:
    """Calcula el mínimo y máximo global de cada campo numérico.

    Args:
        props_list: Lista de dicts ``properties`` de todas las Features.

    Returns:
        Diccionario ``{campo: (min, max)}``.
    """
    stats: dict[str, tuple[float, float]] = {}
    for field in NUMERIC_FIELDS:
        values = np.array([float(p[field]) for p in props_list], dtype=np.float64)
        stats[field] = (float(values.min()), float(values.max()))
        logger.debug("stats[%s] → min=%.2f  max=%.2f", field, *stats[field])
    return stats


def _minmax_norm(value: float, vmin: float, vmax: float, invert: bool = False) -> float:
    """Normaliza un valor al rango [0, 100] con min-max scaling.

    Si ``invert=True`` invierte la escala de forma que el valor máximo
    produce 0.0 y el mínimo produce 100.0 (útil para variables de riesgo).

    Args:
        value:  Valor a normalizar.
        vmin:   Mínimo global del campo.
        vmax:   Máximo global del campo.
        invert: Si True, aplica inversión de escala.

    Returns:
        Float en [0.0, 100.0].
    """
    if vmax == vmin:
        # Todos los valores son iguales; retorna 50 neutral (evita división /0)
        return 50.0

    norm = (value - vmin) / (vmax - vmin)
    if invert:
        norm = 1.0 - norm

    return float(np.clip(norm * 100.0, 0.0, 100.0))


# ---------------------------------------------------------------------------
# 3. Detección de modo producción
# ---------------------------------------------------------------------------


def flag_production_sources() -> bool:
    """Determina si se deben usar fuentes de datos reales (producción).

    Lee la variable de entorno ``URBANIA_PROD_MODE``. Los valores
    reconocidos como *verdadero* son: ``"1"``, ``"true"``, ``"yes"``, ``"on"``
    (sin distinción de mayúsculas/minúsculas).
    Cualquier otro valor (o ausencia de la variable) se interpreta como demo.

    En modo *demo* el pipeline usa exclusivamente el fixture local
    ``mock_fixture.json`` y **no realiza ninguna llamada externa**.

    En modo *producción* (futura integración) se esperaría conectar con:
    - Overpass API (OpenStreetMap) para geometrías actualizadas.
    - DENUE INEGI para actividad económica.
    - SNSP para incidencia delictiva.
    - VIIRS NASA Earth Observation para luminosidad nocturna.
    - GTFS de la CDMX para cobertura de transporte público.

    Returns:
        ``True`` si ``URBANIA_PROD_MODE`` está establecida como verdadera,
        ``False`` en cualquier otro caso.

    Example:
        >>> import os; os.environ["URBANIA_PROD_MODE"] = "true"
        >>> flag_production_sources()
        True
        >>> os.environ["URBANIA_PROD_MODE"] = "0"
        >>> flag_production_sources()
        False
    """
    raw: str = os.environ.get("URBANIA_PROD_MODE", "").strip().lower()
    is_prod: bool = raw in {"1", "true", "yes", "on"}
    logger.info(
        "flag_production_sources: URBANIA_PROD_MODE=%r → prod_mode=%s",
        raw or "(no configurada)",
        is_prod,
    )
    return is_prod


# ---------------------------------------------------------------------------
# 4. Pipeline principal de ingesta
# ---------------------------------------------------------------------------


def run_ingestion(zone_polygon: dict, sector: str) -> list[dict]:
    """Orquesta el pipeline completo de ingesta M1 para una zona y sector.

    Flujo de ejecución
    ------------------
    1. Detecta modo (demo / producción) con ``flag_production_sources()``.
    2. **Modo demo**: localiza el fixture desde su ruta canónica relativa
       al directorio de este módulo y lo carga con ``load_mock_fixture()``.
    3. **Modo producción**: lanza ``NotImplementedError`` (stub para futura
       integración con APIs externas).
    4. Filtra espacialmente las Features que intersectan ``zone_polygon``
       usando Shapely.
    5. Normaliza las Features filtradas con ``normalize_features()``.
    6. Adjunta metadatos de sesión (``sector``, ``prod_mode``, ``total``).

    Args:
        zone_polygon:
            Geometría GeoJSON (``dict``) tipo ``Polygon`` o ``MultiPolygon``
            que define la zona de análisis. Si es ``None`` o ``{}`` se
            devuelven todas las Features del fixture sin filtrar.
        sector:
            Etiqueta de sector de negocio (ej. ``"retail"``, ``"logística"``,
            ``"salud"``). Se adjunta a cada registro como metadato.

    Returns:
        Lista de dicts normalizados enriquecidos con:

        - Todos los campos de ``normalize_features()``.
        - ``"sector"`` → valor del argumento ``sector``.
        - ``"prod_mode"`` → ``bool`` del modo de ejecución.

    Raises:
        FileNotFoundError: Si en modo demo no se encuentra el fixture.
        NotImplementedError: Si se activa modo producción (stub pendiente).
        ValueError: Si ``zone_polygon`` tiene un tipo GeoJSON inválido.

    Example:
        >>> from backend.data.ingest import run_ingestion
        >>> records = run_ingestion(zone_polygon={}, sector="retail")
        >>> len(records)
        50
    """
    prod_mode: bool = flag_production_sources()

    if prod_mode:
        raise NotImplementedError(
            "El modo producción aún no está implementado. "
            "Desactiva URBANIA_PROD_MODE para usar el fixture demo."
        )

    # ── Demo: cargar fixture canónico ──────────────────────────────────────
    fixture_path: Path = (
        Path(__file__).parent / "mock_fixture.json"
    ).resolve()

    geojson: dict = load_mock_fixture(str(fixture_path))
    features: list[dict] = geojson.get("features", [])

    # ── Filtrado espacial con Shapely ──────────────────────────────────────
    filtered_features: list[dict]

    if zone_polygon and zone_polygon.get("coordinates"):
        _validate_zone_polygon(zone_polygon)
        zone_shape = shape(zone_polygon)
        filtered_features = _spatial_filter(features, zone_shape)
        logger.info(
            "run_ingestion: %d/%d features dentro de la zona.",
            len(filtered_features),
            len(features),
        )
    else:
        filtered_features = features
        logger.info(
            "run_ingestion: zone_polygon vacío — usando todas las %d features.",
            len(features),
        )

    # ── Normalizar sobre el subconjunto filtrado ───────────────────────────
    sub_geojson: dict = {
        "type": "FeatureCollection",
        "features": filtered_features,
    }
    normalized: list[dict] = normalize_features(sub_geojson)

    # ── Adjuntar metadatos ─────────────────────────────────────────────────
    for record in normalized:
        record["sector"]    = sector
        record["prod_mode"] = prod_mode

    logger.info(
        "run_ingestion: pipeline M1 completado — %d registros, sector='%s'.",
        len(normalized),
        sector,
    )
    return normalized


# ---------------------------------------------------------------------------
# Helpers privados del pipeline
# ---------------------------------------------------------------------------


def _validate_zone_polygon(zone_polygon: dict) -> None:
    """Valida que zone_polygon sea un GeoJSON Polygon o MultiPolygon.

    Args:
        zone_polygon: Geometría GeoJSON a validar.

    Raises:
        ValueError: Si el tipo no es válido.
    """
    allowed = {"Polygon", "MultiPolygon"}
    gtype = zone_polygon.get("type")
    if gtype not in allowed:
        raise ValueError(
            f"zone_polygon.type debe ser uno de {allowed}, se recibió {gtype!r}."
        )


def _spatial_filter(features: list[dict], zone_shape: Polygon) -> list[dict]:
    """Filtra Features cuya geometría intersecta con ``zone_shape``.

    Usa ``shapely.geometry.shape`` para convertir la geometría GeoJSON a un
    objeto Shapely y luego comprueba intersección con ``.intersects()``.
    Features con geometría inválida se omiten con un aviso en el log.

    Args:
        features:   Lista de Features GeoJSON originales.
        zone_shape: Geometría Shapely de la zona de análisis.

    Returns:
        Subconjunto de ``features`` que intersectan la zona.
    """
    result: list[dict] = []
    for feat in features:
        try:
            feat_shape = shape(feat["geometry"])
            if feat_shape.intersects(zone_shape):
                result.append(feat)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Geometría inválida en Feature '%s' — omitida. (%s)",
                feat.get("id", "?"),
                exc,
            )
    return result
