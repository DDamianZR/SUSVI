const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = {
  analyze: async (sector, params, zonePolygon = null) => {
    const res = await fetch(`${BASE_URL}/api/v1/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sector, params, zone_polygon: zonePolygon })
    });
    if (!res.ok) {
      const errorText = await res.text();
      let errMsg = "Error del servidor";
      try { errMsg = JSON.parse(errorText).detail || errorText; } catch(e) {}
      throw new Error(errMsg);
    }
    return res.json();
  },
  
  getMockZone: async () => {
    const res = await fetch(`${BASE_URL}/api/v1/mock-zone`);
    if (!res.ok) throw new Error("No se pudo cargar la zona base.");
    return res.json();
  },

  health: async () => {
    const res = await fetch(`${BASE_URL}/api/v1/health`);
    if (!res.ok) throw new Error("API no disponible");
    return res.json();
  }
};
