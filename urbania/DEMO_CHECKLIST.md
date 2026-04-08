# Checklist de Verificación PRE-DEMO de URBANIA ✔️

Utiliza esta lista de verificación táctica antes de presentar el MVP al jurado del Hackathon. Verifica que todos los casos base offline y online operan al 100%.

## 1. ⚙️ Pruebas de Sistema y Backend
- [ ] **Fixture Inicial:** El archivo mock (`backend/data/mock_fixture.json`) existe y contiene > 50 features GeoJSON con la metadata estandarizada de polígonos.
- [ ] **Cobertura de Pruebas:** Ejecutar `make test-fast` pasa todos los _asserts_ sin colapsar (Comprobación total de Ingesta, DemandAgent, RiskAgent Math y Business Engine sin uso de LLM).
- [ ] **Despliegue Nativo:** El comando `./scripts/start_demo.sh` levanta exitosamente Vite (localhost:5173) y Uvicorn (localhost:8000) de manera contigua.
- [ ] **Health Endpoint:** Al ingresar a `http://localhost:8000/api/v1/health` retorna un statusCode 200 con `{ "status": "ok" }`.
- [ ] **Demo Seed Instancia:** Endpoint `GET /api/v1/demo-result` responde en < 200ms con el payload algorítmico curado.

## 2. 🗺️ UI Maps & Componentes
- [ ] **Renderizado de Mapa:** El mapa base oscuro carga exitosamente, ubicándose por sobre la CDMX delineando los contornos de las manzanas (sin rellenar si está en Idle).
- [ ] **Toggles Dinámicos:** Los tres switches en el _Control de Capas personalizado_ (Demanda 📊, Riesgo ⚠️, Viabilidad ✅) operan correctamente, mutando las opacidades e interpolando con el estado Z del Leaflet Engine sin sobreponerse erráticamente.
- [ ] **Popups de Interfaz:** Al seleccionar una manzana de las categorizadas (ej. Verde), la caja flotante revela los puntajes financieros relativos y proveé un renglón explicativo derivado del NLP Agent.
- [ ] **Panel de Mapeo "Instant Load":** El botón parpadeante color ámbar de Seed ("Cargar Seed Instantáneo") arranca exitosamente arrojando las métricas, evitando conectividad red. Carga en < 2s.

## 3. 📈 Paneles y Modelos Financieros
- [ ] **Dashboard General:** Luego de un _Analyze_, el panel izquierdo revela las 3 Cards primordiales (`Verdes`, `Cautela`, `Descarte`) alineadas y concordantes con la contabilidad del geoespacio devuelto.
- [ ] **Escenarios IA:** El render de "Escenarios de Despliegue" visualiza 3 enfoques (Agresivo, Conservador, Equilibrado), donde este último sobresale visualmente mostrando su ROI estimado y el Payback Period.
- [ ] **Narrativas Ejecutivas:** El Panel Deslizante de Reporte C-Suite contiene los párrafos, advertencias y pasos recomendables provistos por Watsonx (o el fallback hardcoded local).

## 4. 🖨️ Exportación y Producción de Datos
- [ ] **Merge de GeoJSON:** Al clickar "Exportar Resultados", las propiedades del score cruzado se descargan correctamente como raw text. El GeoJSON debe ser compatible con Kepler.gl.
- [ ] **Generador de Reportes (ReportLab):** Descargar el PDF Ejecutivo expide un documento compilado al instante (vía file pipeline streaming) donde la paleta de colores corporativos se mantiene.
- [ ] **Cero Errores CORS:** Al abrir la consola del navegador (`F12`), ninguna petición a FAST API (`localhost`) o a la acción IBM Cloud bloquea los POSTs. 

---
_Si todos estos recuadros están marcados, ¡Estás oficialmente listo para el Pitch 300x de tu startup tecnológica!_
