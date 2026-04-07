from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from api.config import settings

app = FastAPI(
    title="SUSVI API",
    description="Senderos Urbanos Seguros, Verdes e Inteligentes",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mock_mode": settings.mock_mode,
        "version": "1.0.0"
    }
