"""
Tests unitarios – Módulo M1: Ingesta (backend/data/ingest.py)
=============================================================

Ejecutar desde urbania/backend/:
    pytest tests/test_ingest.py -v

Cobertura de pruebas
--------------------
- load_mock_fixture          : ruta válida, archivo ausente, JSON inválido,
                               tipo incorrecto, campos faltantes, fixtures vacíos.
- normalize_features         : escala [0-100], campo invertido, acceso_gtfs,
                               dataset con valor único (no división por cero),
                               claves presentes en el resultado.
- flag_production_sources    : variable no definida, valores truthy/falsy.
- _minmax_norm               : valores límite y middle.
- run_ingestion              : modo demo sin filtro, zona_polygon vacía,
                               zona_polygon inválida, NotImplementedError en prod.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# ── Garantizar que `backend/` esté en sys.path para imports relativos ────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from data.ingest import (  # noqa: E402
    _compute_stats,
    _minmax_norm,
    _spatial_filter,
    _validate_zone_polygon,
    flag_production_sources,
    load_mock_fixture,
    normalize_features,
    run_ingestion,
)


# ===========================================================================
# ── Fixtures de pytest ───────────────────────────────────────────────────────
# ===========================================================================


def _make_polygon(lon: float, lat: float, delta: float = 0.001) -> dict:
    """Crea un Polygon GeoJSON cuadrado de tamaño ``delta`` centrado en (lon, lat)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon - delta, lat - delta],
            [lon + delta, lat - delta],
            [lon + delta, lat + delta],
            [lon - delta, lat + delta],
            [lon - delta, lat - delta],
        ]],
    }


def _make_feature(
    fid: str = "MZ-T01",
    lon: float = -99.15,
    lat: float = 19.43,
    overrides: dict | None = None,
) -> dict:
    """Retorna una Feature GeoJSON válida con valores realistas."""
    props: dict[str, Any] = {
        "id":                        fid,
        "nombre":                    f"Manzana Test {fid}",
        "lat":                       lat,
        "lng":                       lon,
        "densidad_poblacional":      15000,
        "actividad_economica_denue": 200,
        "luminosidad_viirs":         150,
        "acceso_gtfs":               True,
        "incidencia_delictiva_snsp": 100,
        "tipo_delito_predominante":  "Robo a transeúnte",
        "iluminacion_publica":       70,
        "accesibilidad_logistica":   65,
    }
    if overrides:
        props.update(overrides)

    return {
        "type": "Feature",
        "id": fid,
        "geometry": _make_polygon(lon, lat),
        "properties": props,
    }


def _make_feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


@pytest.fixture()
def single_feature_geojson() -> dict:
    """FeatureCollection con una sola Feature."""
    return _make_feature_collection([_make_feature()])


@pytest.fixture()
def two_feature_geojson() -> dict:
    """FeatureCollection con dos Features de valores distintos."""
    f1 = _make_feature("MZ-A", overrides={"densidad_poblacional": 1000, "incidencia_delictiva_snsp": 10})
    f2 = _make_feature("MZ-B", overrides={"densidad_poblacional": 9000, "incidencia_delictiva_snsp": 500})
    return _make_feature_collection([f1, f2])


@pytest.fixture()
def three_feature_geojson() -> dict:
    """FeatureCollection con tres Features para tests de rango completo."""
    f1 = _make_feature("MZ-1", overrides={
        "densidad_poblacional": 500, "actividad_economica_denue": 0,
        "luminosidad_viirs": 0, "incidencia_delictiva_snsp": 0,
        "iluminacion_publica": 0, "accesibilidad_logistica": 0,
    })
    f2 = _make_feature("MZ-2", overrides={
        "densidad_poblacional": 12000, "actividad_economica_denue": 200,
        "luminosidad_viirs": 127, "incidencia_delictiva_snsp": 250,
        "iluminacion_publica": 50, "accesibilidad_logistica": 50,
    })
    f3 = _make_feature("MZ-3", overrides={
        "densidad_poblacional": 25000, "actividad_economica_denue": 400,
        "luminosidad_viirs": 255, "incidencia_delictiva_snsp": 500,
        "iluminacion_publica": 100, "accesibilidad_logistica": 100,
    })
    return _make_feature_collection([f1, f2, f3])


@pytest.fixture()
def fixture_json_path(three_feature_geojson) -> Path:
    """Escribe un GeoJSON válido en un fichero temporal y retorna su ruta."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        json.dump(three_feature_geojson, fh, ensure_ascii=False)
        return Path(fh.name)


@pytest.fixture()
def real_fixture_path() -> Path:
    """Ruta canónica al mock_fixture.json del proyecto."""
    path = BACKEND_DIR / "data" / "mock_fixture.json"
    if not path.exists():
        pytest.skip("mock_fixture.json no encontrado en backend/data/")
    return path


# ===========================================================================
# ── Tests: load_mock_fixture ─────────────────────────────────────────────────
# ===========================================================================


class TestLoadMockFixture:
    """Pruebas de carga y validación del fixture GeoJSON."""

    def test_carga_fixture_real(self, real_fixture_path: Path) -> None:
        """Debe cargar el fixture del proyecto sin errores."""
        geojson = load_mock_fixture(str(real_fixture_path))
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 50  # fixture tiene 50 manzanas

    def test_carga_fixture_temporal(self, fixture_json_path: Path) -> None:
        """Debe cargar un fixture temporal válido."""
        geojson = load_mock_fixture(str(fixture_json_path))
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 3

    def test_archivo_ausente_lanza_filenotfound(self, tmp_path: Path) -> None:
        """Debe lanzar FileNotFoundError si el archivo no existe."""
        with pytest.raises(FileNotFoundError, match="Fixture no encontrado"):
            load_mock_fixture(str(tmp_path / "no_existe.json"))

    def test_json_invalido_lanza_valueerror(self, tmp_path: Path) -> None:
        """Debe lanzar ValueError si el contenido no es JSON válido."""
        bad = tmp_path / "bad.json"
        bad.write_text("esto no es JSON {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="no es JSON válido"):
            load_mock_fixture(str(bad))

    def test_tipo_incorrecto_lanza_valueerror(self, tmp_path: Path) -> None:
        """Debe rechazar un GeoJSON cuyo type raíz no es FeatureCollection."""
        bad_fc = {"type": "GeometryCollection", "geometries": []}
        bad = tmp_path / "bad_type.json"
        bad.write_text(json.dumps(bad_fc), encoding="utf-8")
        with pytest.raises(ValueError, match="FeatureCollection"):
            load_mock_fixture(str(bad))

    def test_features_vacio_lanza_valueerror(self, tmp_path: Path) -> None:
        """Debe rechazar una FeatureCollection sin Features."""
        empty = {"type": "FeatureCollection", "features": []}
        path = tmp_path / "empty.json"
        path.write_text(json.dumps(empty), encoding="utf-8")
        with pytest.raises(ValueError, match="no contiene ninguna Feature"):
            load_mock_fixture(str(path))

    def test_feature_sin_geometry_lanza_valueerror(self, tmp_path: Path) -> None:
        """Debe rechazar Feature donde geometry es None."""
        feat = _make_feature()
        feat["geometry"] = None
        fc = _make_feature_collection([feat])
        path = tmp_path / "no_geom.json"
        path.write_text(json.dumps(fc), encoding="utf-8")
        with pytest.raises(ValueError, match="geometry es None"):
            load_mock_fixture(str(path))

    def test_feature_campo_faltante_lanza_valueerror(self, tmp_path: Path) -> None:
        """Debe rechazar Feature con un campo obligatorio faltante."""
        feat = _make_feature()
        del feat["properties"]["luminosidad_viirs"]
        fc = _make_feature_collection([feat])
        path = tmp_path / "missing_field.json"
        path.write_text(json.dumps(fc), encoding="utf-8")
        with pytest.raises(ValueError, match="luminosidad_viirs"):
            load_mock_fixture(str(path))

    def test_campo_numerico_tipo_incorrecto(self, tmp_path: Path) -> None:
        """Debe rechazar Feature donde un campo numérico es string."""
        feat = _make_feature(overrides={"densidad_poblacional": "alta"})
        fc = _make_feature_collection([feat])
        path = tmp_path / "bad_type_field.json"
        path.write_text(json.dumps(fc), encoding="utf-8")
        with pytest.raises(ValueError, match="numérico"):
            load_mock_fixture(str(path))

    def test_acceso_gtfs_no_bool(self, tmp_path: Path) -> None:
        """Debe rechazar Feature donde acceso_gtfs no es booleano."""
        feat = _make_feature(overrides={"acceso_gtfs": 1})
        fc = _make_feature_collection([feat])
        path = tmp_path / "bad_gtfs.json"
        path.write_text(json.dumps(fc), encoding="utf-8")
        with pytest.raises(ValueError, match="booleano"):
            load_mock_fixture(str(path))


# ===========================================================================
# ── Tests: normalize_features ────────────────────────────────────────────────
# ===========================================================================


class TestNormalizeFeatures:
    """Pruebas de la normalización min-max de las Features."""

    def test_salida_es_lista(self, single_feature_geojson: dict) -> None:
        """La función debe retornar una lista."""
        result = normalize_features(single_feature_geojson)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_claves_presentes(self, single_feature_geojson: dict) -> None:
        """Cada registro debe contener las claves _raw, _norm y _norm de gtfs."""
        record = normalize_features(single_feature_geojson)[0]
        for field in ("densidad_poblacional", "actividad_economica_denue",
                      "luminosidad_viirs", "incidencia_delictiva_snsp",
                      "iluminacion_publica", "accesibilidad_logistica"):
            assert f"{field}_raw"  in record, f"Falta {field}_raw"
            assert f"{field}_norm" in record, f"Falta {field}_norm"
        assert "acceso_gtfs_raw"  in record
        assert "acceso_gtfs_norm" in record
        assert "geometry"         in record

    def test_rango_0_100_campos_norm(self, three_feature_geojson: dict) -> None:
        """Todos los valores _norm deben estar en [0, 100]."""
        results = normalize_features(three_feature_geojson)
        for record in results:
            for field in ("densidad_poblacional", "actividad_economica_denue",
                          "luminosidad_viirs", "incidencia_delictiva_snsp",
                          "iluminacion_publica", "accesibilidad_logistica"):
                val = record[f"{field}_norm"]
                assert 0.0 <= val <= 100.0, (
                    f"{field}_norm={val!r} fuera de rango en record {record['id']}"
                )

    def test_minimo_tiene_norm_0(self, three_feature_geojson: dict) -> None:
        """La Feature con densidad mínima (MZ-1) debe tener densidad_norm ≈ 0."""
        results = normalize_features(three_feature_geojson)
        by_id = {r["id"]: r for r in results}
        assert by_id["MZ-1"]["densidad_poblacional_norm"] == pytest.approx(0.0, abs=1e-3)

    def test_maximo_tiene_norm_100(self, three_feature_geojson: dict) -> None:
        """La Feature con densidad máxima (MZ-3) debe tener densidad_norm ≈ 100."""
        results = normalize_features(three_feature_geojson)
        by_id = {r["id"]: r for r in results}
        assert by_id["MZ-3"]["densidad_poblacional_norm"] == pytest.approx(100.0, abs=1e-3)

    def test_campo_invertido_incidencia(self, three_feature_geojson: dict) -> None:
        """incidencia_delictiva_snsp está invertida: mínimo delitos → norm 100."""
        results = normalize_features(three_feature_geojson)
        by_id = {r["id"]: r for r in results}
        # MZ-1 tiene mínima incidencia → norm debe ser 100
        assert by_id["MZ-1"]["incidencia_delictiva_snsp_norm"] == pytest.approx(100.0, abs=1e-3)
        # MZ-3 tiene máxima incidencia → norm debe ser 0
        assert by_id["MZ-3"]["incidencia_delictiva_snsp_norm"] == pytest.approx(0.0, abs=1e-3)

    def test_acceso_gtfs_true_norm_100(self, single_feature_geojson: dict) -> None:
        """acceso_gtfs=True debe convertirse a acceso_gtfs_norm=100.0."""
        # La feature de single_feature_geojson tiene acceso_gtfs=True
        record = normalize_features(single_feature_geojson)[0]
        assert record["acceso_gtfs_raw"] is True
        assert record["acceso_gtfs_norm"] == pytest.approx(100.0)

    def test_acceso_gtfs_false_norm_0(self) -> None:
        """acceso_gtfs=False debe convertirse a acceso_gtfs_norm=0.0."""
        fc = _make_feature_collection([_make_feature(overrides={"acceso_gtfs": False})])
        record = normalize_features(fc)[0]
        assert record["acceso_gtfs_raw"] is False
        assert record["acceso_gtfs_norm"] == pytest.approx(0.0)

    def test_dataset_valor_unico_no_division_cero(self) -> None:
        """Si todos los valores de un campo son iguales, no debe lanzar ZeroDivisionError."""
        f1 = _make_feature("U1", overrides={"densidad_poblacional": 5000})
        f2 = _make_feature("U2", overrides={"densidad_poblacional": 5000})
        fc = _make_feature_collection([f1, f2])
        results = normalize_features(fc)
        # Con vmin==vmax → retorna 50.0 neutral
        for r in results:
            assert r["densidad_poblacional_norm"] == pytest.approx(50.0)

    def test_geometria_preservada(self, single_feature_geojson: dict) -> None:
        """La geometría original debe estar intacta en el registro normalizado."""
        original_geom = single_feature_geojson["features"][0]["geometry"]
        record = normalize_features(single_feature_geojson)[0]
        assert record["geometry"] == original_geom

    def test_raw_coincide_con_original(self, two_feature_geojson: dict) -> None:
        """Los valores _raw deben coincidir con los valores originales del fixture."""
        results = normalize_features(two_feature_geojson)
        by_id = {r["id"]: r for r in results}
        assert by_id["MZ-A"]["densidad_poblacional_raw"] == pytest.approx(1000.0)
        assert by_id["MZ-B"]["densidad_poblacional_raw"] == pytest.approx(9000.0)

    def test_geojson_sin_features_lanza_valueerror(self) -> None:
        """Debe lanzar ValueError si el dict no tiene la clave 'features'."""
        with pytest.raises(ValueError, match="'features'"):
            normalize_features({"type": "FeatureCollection"})  # sin key features


# ===========================================================================
# ── Tests: _minmax_norm ──────────────────────────────────────────────────────
# ===========================================================================


class TestMinmaxNorm:
    """Pruebas de la función auxiliar de normalización."""

    def test_valor_minimo(self) -> None:
        assert _minmax_norm(0.0, 0.0, 100.0) == pytest.approx(0.0)

    def test_valor_maximo(self) -> None:
        assert _minmax_norm(100.0, 0.0, 100.0) == pytest.approx(100.0)

    def test_valor_medio(self) -> None:
        assert _minmax_norm(50.0, 0.0, 100.0) == pytest.approx(50.0)

    def test_invertido_minimo_retorna_100(self) -> None:
        assert _minmax_norm(0.0, 0.0, 100.0, invert=True) == pytest.approx(100.0)

    def test_invertido_maximo_retorna_0(self) -> None:
        assert _minmax_norm(100.0, 0.0, 100.0, invert=True) == pytest.approx(0.0)

    def test_clip_sobre_100(self) -> None:
        """Valores fuera de rango deben recortarse a [0, 100]."""
        assert _minmax_norm(150.0, 0.0, 100.0) == pytest.approx(100.0)

    def test_clip_bajo_0(self) -> None:
        assert _minmax_norm(-10.0, 0.0, 100.0) == pytest.approx(0.0)

    def test_vmin_igual_vmax_retorna_50(self) -> None:
        """Cuando min == max el resultado debe ser 50.0 (neutral)."""
        assert _minmax_norm(5.0, 5.0, 5.0) == pytest.approx(50.0)


# ===========================================================================
# ── Tests: flag_production_sources ───────────────────────────────────────────
# ===========================================================================


class TestFlagProductionSources:
    """Pruebas de detección de modo producción."""

    def _set_env(self, value: str | None) -> None:
        if value is None:
            os.environ.pop("URBANIA_PROD_MODE", None)
        else:
            os.environ["URBANIA_PROD_MODE"] = value

    def teardown_method(self, _method) -> None:  # noqa: ANN001
        """Limpia la variable de entorno después de cada test."""
        os.environ.pop("URBANIA_PROD_MODE", None)

    def test_sin_variable_es_false(self) -> None:
        """Sin variable de entorno debe retornar False (modo demo)."""
        self._set_env(None)
        assert flag_production_sources() is False

    @pytest.mark.parametrize("truthy_val", ["1", "true", "True", "TRUE", "yes", "YES", "on", "ON"])
    def test_valores_truthy(self, truthy_val: str) -> None:
        """Valores considerados 'verdaderos' deben retornar True."""
        self._set_env(truthy_val)
        assert flag_production_sources() is True

    @pytest.mark.parametrize("falsy_val", ["0", "false", "False", "no", "off", "", "   "])
    def test_valores_falsy(self, falsy_val: str) -> None:
        """Valores no reconocidos como verdaderos deben retornar False."""
        self._set_env(falsy_val)
        assert flag_production_sources() is False

    def test_retorno_es_bool(self) -> None:
        """El valor retornado debe ser estrictamente bool."""
        self._set_env("true")
        result = flag_production_sources()
        assert isinstance(result, bool)


# ===========================================================================
# ── Tests: run_ingestion ─────────────────────────────────────────────────────
# ===========================================================================


class TestRunIngestion:
    """Pruebas del pipeline de ingesta completo."""

    def teardown_method(self, _method) -> None:  # noqa: ANN001
        os.environ.pop("URBANIA_PROD_MODE", None)

    def test_modo_demo_sin_filtro(self, real_fixture_path: Path) -> None:
        """En modo demo con zone_polygon vacío debe retornar todas las manzanas."""
        os.environ.pop("URBANIA_PROD_MODE", None)
        records = run_ingestion(zone_polygon={}, sector="retail")
        assert len(records) == 50

    def test_metadatos_sector(self, real_fixture_path: Path) -> None:
        """Cada registro debe contener el campo 'sector' con el valor pasado."""
        records = run_ingestion(zone_polygon={}, sector="logística")
        for r in records:
            assert r["sector"] == "logística"

    def test_metadatos_prod_mode_false(self, real_fixture_path: Path) -> None:
        """En modo demo cada registro debe tener prod_mode=False."""
        records = run_ingestion(zone_polygon={}, sector="salud")
        for r in records:
            assert r["prod_mode"] is False

    def test_modo_produccion_lanza_not_implemented(self) -> None:
        """Con URBANIA_PROD_MODE=true debe lanzar NotImplementedError."""
        os.environ["URBANIA_PROD_MODE"] = "true"
        with pytest.raises(NotImplementedError):
            run_ingestion(zone_polygon={}, sector="retail")

    def test_zone_polygon_invalido_lanza_valueerror(self) -> None:
        """Un zone_polygon con type incorrecto debe lanzar ValueError."""
        bad_zone = {"type": "Point", "coordinates": [-99.15, 19.43]}
        with pytest.raises(ValueError, match="zone_polygon.type"):
            run_ingestion(zone_polygon=bad_zone, sector="retail")

    def test_filtrado_espacial_reduce_features(self, real_fixture_path: Path) -> None:
        """Un zone_polygon pequeño debe retornar menos de 50 registros."""
        # Zona muy pequeña centrada en MZ-001 (-99.1495, 19.4325)
        small_zone = _make_polygon(-99.1495, 19.4325, delta=0.0005)
        records = run_ingestion(zone_polygon=small_zone, sector="retail")
        assert len(records) < 50

    def test_filtrado_espacial_zona_fuera_retorna_vacio(self, real_fixture_path: Path) -> None:
        """Una zona completamente fuera del fixture debe retornar lista vacía."""
        far_zone = _make_polygon(0.0, 0.0, delta=0.001)  # África occidental
        records = run_ingestion(zone_polygon=far_zone, sector="retail")
        assert records == []

    def test_resultado_es_lista_de_dicts(self, real_fixture_path: Path) -> None:
        """El resultado debe ser una lista de dicts."""
        records = run_ingestion(zone_polygon={}, sector="test")
        assert isinstance(records, list)
        assert all(isinstance(r, dict) for r in records)
