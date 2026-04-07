# Dataset Mock — SUSVI

Zona de demostración: **Tepito, Alcaldía Cuauhtémoc, CDMX**
- 22 manzanas
- 9,200 habitantes estimados
- Índice de riesgo promedio: 72.3/100
- Cobertura lumínica actual: 37%

## Archivos

| Archivo | Contenido |
|---|---|
| `tepito_mock.geojson` | Polígonos de manzanas con índice de riesgo y datos lumínicos |
| `poi_mock.geojson` | Puntos de interés: escuela, clínica, mercado, metro |
| `luminarias_mock.geojson` | Luminarias existentes con estado (activa/apagada) |
| `red_vial_mock.geojson` | Red vial peatonal con anchuras de banqueta |

## Activar modo mock

En `.env`:
```
MOCK_MODE=true
```

En producción, cambiar a `MOCK_MODE=false` para usar fuentes reales (OSM, SNSP, DENUE).
