# URBANIA – Plataforma SaaS B2B de Inteligencia Territorial

> Motor de análisis territorial impulsado por IBM Watsonx AI (Granite 13B) con 3 agentes especializados: **Demanda**, **Riesgo** y **Negocios**.

---

## 📂 Estructura del Proyecto

```
urbania/
├── frontend/               ← React + Vite + Tailwind + Leaflet.js + D3.js
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map/        ← Mapa Leaflet interactivo (GeoJSON)
│   │   │   ├── Dashboard/  ← KPIs y gráficas D3
│   │   │   ├── Scores/     ← Ranking de manzanas
│   │   │   └── Reports/    ← Generación de PDF ejecutivo
│   │   ├── hooks/          ← Custom hooks (useFixture, useAnalysis, …)
│   │   ├── services/       ← Llamadas a la API backend
│   │   └── utils/          ← Helpers, normalización, colores
│   └── public/mock_data/   ← Fixture GeoJSON (demo sin CORS)
└── backend/                ← FastAPI + Python
    ├── agents/
    │   ├── demand_agent.py  ← Score de Demanda (DENUE, VIIRS, GTFS)
    │   ├── risk_agent.py    ← Score de Riesgo (SNSP, iluminación)
    │   └── business_agent.py← Oportunidad compuesta + recomendación
    ├── routes/
    │   ├── analysis.py      ← GET /api/analysis/full|demand|risk|business
    │   ├── geojson_export.py← GET /api/geojson/enriched|raw
    │   └── report.py        ← GET /api/report/pdf
    └── data/mock_fixture.json
```

---

## 🚀 Instalación y Arranque

### Prerrequisitos

| Herramienta | Versión mínima |
|-------------|----------------|
| Node.js     | 20 LTS         |
| Python      | 3.11+          |
| pip         | 23+            |

---

### 1 · Frontend

```bash
cd urbania/frontend

# Instalar dependencias
npm install

# Arrancar servidor de desarrollo (http://localhost:5173)
npm run dev
```

> El frontend hace proxy automático de `/api/*` → `http://localhost:8000` (configurado en `vite.config.js`).

---

### 2 · Backend

```bash
cd urbania/backend

# Crear entorno virtual (recomendado)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Arrancar servidor FastAPI (http://localhost:8000)
uvicorn main:app --reload
```

---

### 3 · Verificar instalación

Abrir en el navegador:

| URL | Descripción |
|-----|-------------|
| `http://localhost:5173` | Frontend URBANIA |
| `http://localhost:8000/api/health` | Health-check backend |
| `http://localhost:8000/api/fixture` | Fixture GeoJSON raw |
| `http://localhost:8000/api/analysis/full` | Análisis completo (3 agentes) |
| `http://localhost:8000/api/geojson/enriched` | GeoJSON enriquecido para Leaflet |
| `http://localhost:8000/api/report/pdf` | Descargar PDF ejecutivo |
| `http://localhost:8000/docs` | Swagger UI automático |

---

## 🗺️ Fixture de Demo

El archivo `mock_fixture.json` contiene **50 manzanas** de la **Zona Piloto CDMX** como `FeatureCollection` GeoJSON válido (RFC 7946), con coordenadas reales en EPSG:4326 alrededor del centro de Ciudad de México.

Cada Feature incluye:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `densidad_poblacional` | number | hab/km² |
| `actividad_economica_denue` | number | Establecimientos según DENUE |
| `luminosidad_viirs` | number | Índice VIIRS nocturno (0–255) |
| `acceso_gtfs` | boolean | Cobertura de transporte público |
| `incidencia_delictiva_snsp` | number | Delitos últimos 12 meses |
| `tipo_delito_predominante` | string | Categoría de delito principal |
| `iluminacion_publica` | number | Porcentaje cobertura (0–100) |
| `accesibilidad_logistica` | number | Score logístico (0–100) |

### Distribución de manzanas

| Tipo | Ejemplos | Características |
|------|----------|-----------------|
| 🟢 **INVERTIR** | Reforma Norte, Roma Norte, Condesa, Polanco | Alta demanda + bajo riesgo |
| 🟡 **CAUTELA** | Centro Histórico, Garibaldi, Escandón | Alta demanda + riesgo medio |
| 🟣 **EVALUAR** | Narvarte, Coyoacán, Del Valle | Demanda media + riesgo bajo |
| 🔴 **DESCARTAR** | Tepito, Iztapalapa, Morelos, Bondojito | Alto riesgo + baja calidad |

---

## 🤖 Agentes Watsonx

Los agentes operan en **modo demo** (sin API key) retornando narrativas precargadas. Para activar IBM Watsonx en producción:

1. Crear un archivo `.env` en `urbania/backend/`:

```env
WATSONX_API_KEY=tu_api_key_aqui
WATSONX_PROJECT_ID=tu_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

2. Instanciar el cliente en `main.py` y pasarlo a cada agente.

---

## 📤 Outputs

| Output | Endpoint | Formato |
|--------|----------|---------|
| GeoJSON enriquecido | `/api/geojson/enriched` | `application/geo+json` |
| Análisis completo | `/api/analysis/full` | JSON |
| Reporte ejecutivo | `/api/report/pdf` | PDF (ReportLab) |

---

## Licencia

Uso interno – Propuesta de desarrollo URBANIA © 2024
