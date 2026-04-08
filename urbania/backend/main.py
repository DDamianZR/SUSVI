"""
URBANIA – Backend principal
FastAPI application entrypoint.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("urbania")

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="URBANIA API",
    description="Plataforma SaaS B2B de inteligencia territorial",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Fixture ──────────────────────────────────────────────────────────────────
FIXTURE_PATH = Path(__file__).parent / "data" / "mock_fixture.json"

def load_fixture() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)

# ── Routes (importar después del app para evitar circular imports) ────────────
from routes import analysis, geojson_export, report  # noqa: E402

app.include_router(analysis.router,       prefix="/api/analysis",  tags=["Analysis"])
app.include_router(geojson_export.router, prefix="/api/geojson",   tags=["GeoJSON"])
app.include_router(report.router,         prefix="/api/report",    tags=["Report"])


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/fixture", tags=["Fixture"])
def get_fixture():
    """Retorna el fixture completo como GeoJSON FeatureCollection."""
    return load_fixture()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
