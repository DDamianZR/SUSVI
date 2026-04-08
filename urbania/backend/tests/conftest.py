import os
import pytest
from unittest import mock
import random
import uuid

@pytest.fixture
def mock_features():
    """Retorna 10 features normalizadas para tests rápidos offline."""
    features = []
    for i in range(10):
        features.append({
            "id": str(uuid.uuid4()),
            "densidad_poblacional_norm": random.uniform(10, 90),
            "actividad_economica_denue_norm": random.uniform(10, 90),
            "luminosidad_viirs_norm": random.uniform(10, 90),
            "incidencia_delictiva_snsp_norm": random.uniform(10, 90),
            "acceso_gtfs_norm": random.uniform(10, 90),
            "ingreso_estimado_norm": random.uniform(10, 90),
            "iluminacion_publica_norm": random.uniform(10, 90),
            "accesibilidad_logistica_norm": random.uniform(10, 90)
        })
    return features

@pytest.fixture
def sample_params():
    """Parametros financieros de ejemplo."""
    return {
        "ticket_inversion_mxn": 500000,
        "vida_util_anios": 5,
        "tasa_descuento": 0.12,
        "n_unidades_objetivo": 10
    }

@pytest.fixture
def watsonx_disabled():
    """Context manager que mockea Watsonx forzando PROD_MODE=0."""
    with mock.patch.dict(os.environ, {"URBANIA_PROD_MODE": "0"}):
        yield
