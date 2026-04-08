// ─── URBANIA API Service ────────────────────────────────────────────────────
// Usa el proxy de Vite (/api → http://localhost:8000) en desarrollo.
// En produccion, sobreescribe VITE_API_BASE_URL en el entorno.

const BASE = '';  // Vite proxy maneja /api/* → localhost:8000

async function _fetch(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try { detail = JSON.parse(text).detail || text; } catch (_) {}
    throw new Error(detail);
  }
  return res;
}

export const api = {
  // ── Health & Status ────────────────────────────────────────────────────
  health: async () => {
    const res = await _fetch(`${BASE}/api/v1/health`);
    return res.json();
  },

  // ── Zona base (mapa inicial sin análisis) ──────────────────────────────
  getMockZone: async () => {
    const res = await _fetch(`${BASE}/api/v1/mock-zone`);
    return res.json();
  },

  // ── Análisis completo (3 agentes) ─────────────────────────────────────
  analyze: async (sector, params, zonePolygon = null) => {
    const res = await _fetch(`${BASE}/api/v1/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sector, params, zone_polygon: zonePolygon })
    });
    return res.json();
  },

  // ── Demo seed pre-calculado ────────────────────────────────────────────
  getDemoResult: async () => {
    const res = await _fetch(`${BASE}/api/v1/demo-result`);
    return res.json();
  },

  // ── Exportaciones ──────────────────────────────────────────────────────
  exportGeoJSON: async (analysisId) => {
    const res = await _fetch(`${BASE}/api/v1/export/geojson`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId })
    });
    return res.blob();
  },

  exportPDF: async (analysisId) => {
    const res = await _fetch(`${BASE}/api/v1/export/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId, format: 'pdf' })
    });
    return res.blob();
  },

  exportRawData: async (analysisId) => {
    const res = await _fetch(`${BASE}/api/v1/export/raw-data/${analysisId}`);
    return res.json();
  }
};
