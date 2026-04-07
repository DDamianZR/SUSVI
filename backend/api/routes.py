from fastapi import APIRouter

router = APIRouter()

@router.post("/analizar")
async def analizar_zona(zona: dict):
    """Recibe coordenadas y retorna diagnóstico + escenarios."""
    # TODO: conectar M1 → M2 → M3
    return {"status": "pendiente", "mensaje": "Módulo en desarrollo"}

@router.get("/escenarios/{zona_id}")
async def obtener_escenarios(zona_id: str):
    """Retorna los 3 escenarios generados para una zona."""
    # TODO: consultar caché o regenerar
    return {"zona_id": zona_id, "escenarios": []}

@router.get("/mock/zonas")
async def listar_zonas_mock():
    """Lista las zonas disponibles en el dataset mock."""
    return {"zonas": ["tepito_mock"]}
