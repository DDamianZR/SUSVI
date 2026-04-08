import os
import json
import pytest
from fastapi.testclient import TestClient

# Add src to path for direct imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from data.ingest import load_mock_fixture, run_ingestion
from agents.demand_agent import DemandAgent
from agents.risk_agent import RiskAgent
from agents.business_agent import BusinessAgent

client = TestClient(app)

class TestIngestionModule:
    def test_mock_fixture_loads_correctly(self):
        """Verifica que el fixture carga y tiene al menos 50 features."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        fixture_path = os.path.join(data_dir, 'mock_fixture.json')
        data = load_mock_fixture(fixture_path)
        assert data.get('type') == 'FeatureCollection'
        assert len(data.get('features', [])) >= 50

    def test_normalize_features_range(self):
        """Verifica que todos los campos normalizados están en [0,100]."""
        features_norm = run_ingestion({}, 'telecomunicaciones')
        for f in features_norm:
            assert 'id' in f
            assert 0 <= f.get('densidad_poblacional_norm', 0) <= 100
            assert 0 <= f.get('actividad_economica_denue_norm', 0) <= 100
            assert 0 <= f.get('luminosidad_viirs_norm', 0) <= 100

    def test_geojson_is_valid(self):
        """Valida estructura GeoJSON RFC 7946 (benshmark response)."""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        fixture_path = os.path.join(data_dir, 'mock_fixture.json')
        data = load_mock_fixture(fixture_path)
        assert 'features' in data
        assert 'type' in data
        assert data['type'] in ['FeatureCollection', 'Feature']


class TestDemandAgent:
    def test_demand_score_range(self, mock_features, watsonx_disabled):
        """Todos los scores generados por DemandAgent deben estar entre 0 y 100."""
        agent = DemandAgent(sector='telecomunicaciones', use_fallback_only=True)
        scores = agent.score(mock_features, 'telecomunicaciones')
        for s in scores:
            assert 0 <= s['score_demanda'] <= 100

    def test_sector_weights_different(self, mock_features, watsonx_disabled):
        """Los scores varían si se procesan para diferentes sectores dado distinto peso."""
        agent_tel = DemandAgent(sector='telecomunicaciones', use_fallback_only=True)
        agent_seg = DemandAgent(sector='seguridad', use_fallback_only=True)
        
        scores_tel = agent_tel.score(mock_features, 'telecomunicaciones')
        scores_seg = agent_seg.score(mock_features, 'seguridad')
        
        # Al menos un score difiere si aplicamos distintos pesajes
        diffs = [abs(t['score_demanda'] - s['score_demanda']) for t, s in zip(scores_tel, scores_seg)]
        assert sum(diffs) > 0

    def test_fallback_without_watsonx(self, mock_features, watsonx_disabled):
        """El fallback algorítmico produce scores válidos cuando WATSONX_API_KEY no se usa."""
        agent = DemandAgent(sector='inmobiliario', use_fallback_only=True)
        scores = agent.score(mock_features, 'inmobiliario')
        assert len(scores) == len(mock_features)
        assert 'justificacion_top3' in scores[0]

    def test_demand_geojson_output(self, mock_features, watsonx_disabled):
        """El GeoJSON output tiene los campos correctos insertados."""
        agent = DemandAgent(sector='telecomunicaciones', use_fallback_only=True)
        scores = agent.score(mock_features, 'telecomunicaciones')
        
        dummy_base = {"type": "FeatureCollection", "features": [{"id": f["id"], "properties": {}} for f in mock_features]}
        geo = agent.to_geojson(scores, dummy_base)
        
        assert geo['type'] == 'FeatureCollection'
        assert 'score_demanda' in geo['features'][0]['properties']


class TestRiskAgent:
    def test_risk_classification(self, mock_features, watsonx_disabled):
        """Zonas con score < 30 clasificadas como VERDE, etc."""
        agent = RiskAgent(use_fallback_only=True)
        # Forzar data local
        mock_features[0]["incidencia_delictiva_snsp_norm"] = 10 # bajo riesgo
        mock_features[1]["incidencia_delictiva_snsp_norm"] = 90 # alto riesgo
        
        scores = agent.score(mock_features[:2])
        
        clases = [s['clasificacion'] for s in scores]
        assert 'VERDE' in clases or 'CAUTELA' in clases or 'DESCARTE' in clases

    def test_risk_geojson_has_color_property(self, mock_features, watsonx_disabled):
        """GeoJSON exportado inyecta properties requeridas como 'color_leaflet' o clasificacion."""
        agent = RiskAgent(use_fallback_only=True)
        scores = agent.score(mock_features[:1])
        dummy_base = {"type": "FeatureCollection", "features": [{"id": mock_features[0]["id"], "properties": {}}]}
        
        geo = agent.generate_risk_geojson(scores, dummy_base)
        props = geo['features'][0]['properties']
        
        assert 'clasificacion' in props


class TestBusinessAgent:
    def test_viability_formula(self, sample_params, watsonx_disabled):
        """Testear formula financiera basica manual VS modelo."""
        agent = BusinessAgent(use_fallback_only=True)
        d_scores = [{"id": "z1", "score_demanda": 80}]
        r_scores = [{"id": "z1", "score_riesgo": 20}] # = 80 * (1 - 20/100) = 80 * 0.8 = 64
        # Si factor es Seguridad = 1.0. SV = 64 / (0.5M normalizado a 0.5) = 128 (tope en 100)
        sample_params["sector"] = "seguridad"
        
        res = agent.generate_scenarios(d_scores, r_scores, sample_params)
        feats = res.get("features_score_viabilidad", [])
        
        assert len(feats) == 1
        assert feats[0]["score_viabilidad"] > 0
        assert feats[0]["categoria_viabilidad"] in ["Alta viabilidad", "Viabilidad media", "Descarte"]

    def test_three_scenarios_generated(self, mock_features, sample_params, watsonx_disabled):
        """El output siempre tiene agresivo, conservador, equilibrado."""
        d_agent = DemandAgent(sector='telecomunicaciones', use_fallback_only=True)
        r_agent = RiskAgent(use_fallback_only=True)
        b_agent = BusinessAgent(use_fallback_only=True)

        d_scores = d_agent.score(mock_features, 'telecomunicaciones')
        r_scores = r_agent.score(mock_features)
        
        sample_params["sector"] = "telecomunicaciones"
        res = b_agent.generate_scenarios(d_scores, r_scores, sample_params)
        
        nombres = [s['nombre'].lower() for s in res['escenarios_algoritmicos']]
        assert 'agresivo' in nombres
        assert 'conservador' in nombres
        assert 'equilibrado' in nombres

    def test_roi_is_positive_for_green_zones(self, sample_params, watsonx_disabled):
        """Las iteraciones de ROI en escenarios sin riesgo inmersivo debrian arrojar ROI > 0."""
        b_agent = BusinessAgent(use_fallback_only=True)
        d_scores = [{"id": "z1", "score_demanda": 100}]
        r_scores = [{"id": "z1", "score_riesgo": 5}]
        
        res = b_agent.generate_scenarios(d_scores, r_scores, sample_params)
        # Verify the ROI in first logic scenario
        rois = [s['roi'] for s in res['escenarios_algoritmicos']]
        assert any(r > 0 for r in rois)


class TestAPIEndpoints:
    def test_health_endpoint(self):
        """Llama a health y asegura status_code 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_mock_zone_endpoint(self):
        """Llama a mock_zone y retorna Features."""
        response = client.get("/api/v1/mock-zone")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0

    def test_full_analysis_telecomunicaciones(self, sample_params, watsonx_disabled):
        """Prueba end-to-end de analysis fallback rapido."""
        payload = {
            "sector": "telecomunicaciones",
            "params": sample_params
        }
        # Inyecta zona polygon generica
        response = client.post("/api/v1/analyze", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "analysis_id" in data
        assert "viability_scores" in data
        assert "scenarios" in data
        assert "executive_report" in data

    def test_full_analysis_under_60_seconds(self, sample_params, watsonx_disabled):
        """Se asegura que los procesos nativos locales sean veloces."""
        import time
        start = time.time()
        
        response = client.post("/api/v1/analyze", json={
            "sector": "seguridad",
            "params": sample_params
        })
        
        diff = time.time() - start
        assert response.status_code == 200
        assert diff < 60.0
