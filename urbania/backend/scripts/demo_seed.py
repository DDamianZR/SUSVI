import os
import sys
import json
import asyncio
from datetime import datetime, timezone
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.ingest import load_mock_fixture, run_ingestion
from agents.demand_agent import DemandAgent
from agents.risk_agent import RiskAgent
from agents.business_agent import BusinessAgent
from utils.pdf_generator import URBANIAReportGenerator

def main():
    print("🚀 Iniciando Seed de Demo para Hackathon URBANIA...")
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    fixture_path = os.path.join(data_dir, 'mock_fixture.json')
    cache_path = os.path.join(data_dir, 'demo_cache.json')
    result_path = os.path.join(data_dir, 'demo_result.json')
    pdf_path = os.path.join(data_dir, 'demo_report.pdf')

    # 1. Verificar fixture
    if not os.path.exists(fixture_path):
        print(f"❌ Error: Fixture no encontrado: {fixture_path}")
        sys.exit(1)
        
    fixture = load_mock_fixture(fixture_path)
    if len(fixture.get("features", [])) < 50:
        print("❌ Error: El fixture no tiene al menos 50 features.")
        sys.exit(1)
        
    print(f"✅ Fixture OK: {len(fixture['features'])} features cargadas.")

    # 2. Pre-calcular scores
    sector = "telecomunicaciones"
    print(f"⚙️ Ingestando y modelando matemáticamente sector: {sector} (Fallback mode)...")
    
    features_norm = run_ingestion({}, sector)
    
    demand_agent = DemandAgent(sector=sector, use_fallback_only=True)
    risk_agent = RiskAgent(use_fallback_only=True)
    business_agent = BusinessAgent(use_fallback_only=True)

    demand_scores = demand_agent.score(features_norm, sector)
    risk_scores = risk_agent.score(features_norm)

    demo_cache = {
        "demand_scores": demand_scores,
        "risk_scores": risk_scores,
        "sector": sector,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(demo_cache, f, ensure_ascii=False)
    print(f"✅ Demo Cache guardado: {cache_path}")

    # 3. Generar analisis de demo completo
    params = {
        "ticket_inversion_mxn": 500000,
        "vida_util_anios": 5,
        "tasa_descuento": 0.12,
        "sector": sector,
        "n_unidades_objetivo": 20
    }
    business_results = business_agent.generate_scenarios(demand_scores, risk_scores, params)

    demand_geojson = demand_agent.to_geojson(demand_scores, fixture)
    risk_geojson = risk_agent.generate_risk_geojson(risk_scores, fixture)
    
    viables = []
    for feat in business_results.get("features_score_viabilidad", []):
        viables.append({
            "id": feat["id"],
            "score_viabilidad": feat["score_viabilidad"],
            "clasificacion": feat["categoria_viabilidad"]
        })

    analysis_id = "DEMO-HACKATHON-XOLUM"
    demo_result = {
        "analysis_id": analysis_id,
        "demand_geojson": demand_geojson,
        "risk_geojson": risk_geojson,
        "viability_scores": viables,
        "scenarios": business_results.get("escenarios_algoritmicos", []),
        "executive_report": business_results.get("reporte_ejecutivo", {}),
        "metadata": {
            "sector": sector,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_manzanas_analizadas": len(features_norm),
            "demo_mode": True
        }
    }

    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(demo_result, f, ensure_ascii=False)
    print(f"✅ Demo Result guardado: {result_path}")

    # 4. KPI Calcs for PDF
    kpis = {
        "verdes": len([v for v in viables if v["clasificacion"] == "Alta viabilidad"]),
        "cautela": len([v for v in viables if v["clasificacion"] == "Viabilidad media"]),
        "descarte": len([v for v in viables if v["clasificacion"] == "Descarte"])
    }
    
    pdf_dict = business_agent.to_pdf_ready_dict({"reporte_ejecutivo": demo_result["executive_report"]})
    pdf_dict.update({
        "analysis_id": analysis_id,
        "metadata": demo_result["metadata"],
        "kpis": kpis
    })

    generator = URBANIAReportGenerator()
    generator.generate(pdf_dict, pdf_path)
    print(f"✅ Demo Report PDF guardado: {pdf_path}")

    # 5. Imprimir Resumen
    equilibrado = next((s for s in demo_result["scenarios"] if s["nombre"] == "Equilibrado"), demo_result["scenarios"][-1])
    ahorro = equilibrado.get("ahorro_vs_aleatorio", 0) * 1000000

    print("\n" + "="*50)
    print("📊 RESUMEN EJECUTIVO DEMO")
    print("="*50)
    print(f"🟢 Zonas Verdes:   {kpis['verdes']}")
    print(f"🟡 Zonas Cautela:  {kpis['cautela']}")
    print(f"🔴 Zonas Descarte: {kpis['descarte']}")
    print("-" * 50)
    print(f"🏅 Escenario Seleccionado: {equilibrado.get('nombre')}")
    print(f"📈 ROI Promedio:   {equilibrado.get('roi')}%")
    print(f"⏳ Payback Est.:   {equilibrado.get('payback')} años")
    print(f"💰 Ahorro vs Rnd:  ${ahorro:,.0f} MXN")
    print("-" * 50)
    print(f"📄 Ruta del PDF:   {pdf_path}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
