# Referencia de API REST — URBANIA

> **Nota de Autenticación (Producción)**: El API B2B de URBANIA requiere para endpoints productivos del token de autorización `Bearer <JWT>` que se inyecta en la cabecera `Authorization`. Sin embargo, en entornos Demo/Testing actual, no se requiere auth en los headers.

---

## 1. POST `/api/v1/analyze`

**Descripción**: Orquesta el procesamiento paralelo geográfico y la IA Watsonx. Extrae información territorial basada en el polígono, calcula demanda cruzada por sector y procesa riesgos de despliegue para generar variables unificadas.

**Request Payload**:
```json
{
  "zone_polygon": null, // o dict GeoJSON Type: Polygon
  "sector": "telecomunicaciones", // "telecomunicaciones" | "seguridad" | "inmobiliario"
  "params": {
    "ticket_inversion_mxn": 500000,
    "vida_util_anios": 5,
    "tasa_descuento": 0.12,
    "n_unidades_objetivo": 20
  }
}
```

**Response (200 OK)**:
```json
{
  "analysis_id": "c3a20-b44c-4e89-1234",
  "demand_geojson": { ... },     // GeoJSON crudo con props: `score_demanda`
  "risk_geojson": { ... },       // GeoJSON crudo con props: `clasificacion`, `color_leaflet`
  "viability_scores": [
    {
      "id": "manzana_139",
      "score_viabilidad": 84.5,
      "clasificacion": "Alta viabilidad"
    }
  ],
  "scenarios": [
    {
      "nombre": "Equilibrado",
      "recomendacion_narrativa": "...",
      "roi": 12.4,
      ...
    }
  ],
  "executive_report": { 
     "resumen_ejecutivo": "...",
     "advertencias": [] 
  },
  "metadata": {
    "sector": "telecomunicaciones",
    "timestamp": "2026-04-08T10:00:00Z"
  }
}
```

---

## 2. GET `/api/v1/demo-result`

**Descripción**: Retorna la caché instantánea local de los algoritmos de fallback para simulaciones en frontend sin latencia de inferencia Llama/Granite (~0ms return time).

**Response (200 OK)**: Misma estructura exacta al objeto consolidado de `/api/v1/analyze`.

---

## 3. GET `/api/v1/mock-zone`

**Descripción**: Retorna el fixture original GeoJSON (coordenadas brutas y properties de origen) de la Ciudad de México u otra ciudad de demo para poder renderizar las líneas de contorno visual initial.

---

## 4. GET `/api/v1/health`

**Descripción**: Latency y ping test al endpoint de IBM/Watsonx así como disponibilidad matemática local.

**Response (200 OK)**:
```json
{
  "status": "ok",
  "watsonx_prod_enabled": false,
  "watsonx_network_ok": true,
  "timestamp": "2026-04-08T10:20:00Z"
}
```

---

## 5. POST `/api/v1/export/geojson`

**Descripción**: Genera y exporta la fusión cruzada de los tres agentes hacia un unico archivo universal GeoJSON, compatible con QGIS y Kepler.GL.

**Request Payload**:
```json
{
  "analysis_id": "c3a20-b44c..."
}
```

**Comportamiento**: Devuelve string `application/json` unificado sumando propiedades como `score_riesgo`, `clasificacion_riesgo`, `score_viabilidad` a la matriz base. Si el UI especulamente quiere descargarlo, usa Headers Content-Disposition `attachment`.

---

## 6. POST `/api/v1/export/report`

**Descripción**: Gatillo binario/backend para que la libreria ReportLab convierta el resultado analítico complejo a un PDF amigable para Directivos.

**Request Payload**:
```json
{
  "analysis_id": "c3a20-b44c...",
  "format": "pdf" 
}
```

**Comportamiento**: 
- Si `format = "json" | "pdf_ready"`: Devuelve un JSON curado de inyección
- Si `format = "pdf"`: Devuelve directamente el blob de un `.pdf` (headers application/pdf) listo para descarga asíncrona del file system.
