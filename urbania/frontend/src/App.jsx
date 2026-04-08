import React, { useState, useEffect } from 'react';
import { Layers, Activity, AlertTriangle, X } from 'lucide-react';
import UrbaniaMap from './components/Map/UrbaniaMap.jsx';
import { useMapData } from './hooks/useMapData.js';
import SectorSelector from './components/Dashboard/SectorSelector.jsx';
import MetricsPanel from './components/Dashboard/MetricsPanel.jsx';
import ScenariosPanel from './components/Dashboard/ScenariosPanel.jsx';
import ExecutiveReportPanel from './components/Dashboard/ExecutiveReportPanel.jsx';
import { api } from './services/api.js';

export default function App() {
  const [analysisState, setAnalysisState] = useState('idle'); // idle | loading | complete | error
  const [errorMessage, setErrorMessage] = useState('');
  
  const [health, setHealth] = useState({ ok: false, mock_mode: true });
  const [baseGeoJSON, setBaseGeoJSON] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  
  const [selectedScenarioId, setSelectedScenarioId] = useState('EQUILIBRADO');

  // Hook que administra la data a proyectar
  const { 
    mapData, 
    activeLayer, 
    setActiveLayer, 
    selectedZone, 
    setSelectedZone 
  } = useMapData(analysisResult);

  // Inicializacion
  useEffect(() => {
    const initApp = async () => {
      try {
        const hRes = await api.health();
        setHealth({ ok: hRes.status === 'ok', mock_mode: hRes.mock_mode });
        
        // Carga la zona base para dar contexto visual vacio antes del análsis
        const mockLayer = await api.getMockZone();
        setBaseGeoJSON(mockLayer);
      } catch (e) {
        console.error("Error al iniciar la app", e);
      }
    };
    initApp();
  }, []);

  const handleAnalyze = async (sector, params) => {
    setAnalysisState('loading');
    setErrorMessage('');
    setAnalysisResult(null);
    setSelectedZone(null);
    try {
      // Opcional: si existe un polygone trimmings, se envía en zonePolygon (estático en UI base)
      const res = await api.analyze(sector, params, null);
      
      setAnalysisResult(res);
      setSelectedScenarioId('EQUILIBRADO'); // Default post reset
      setAnalysisState('complete');
    } catch (e) {
      setErrorMessage(e.message || "Error desconocido al contactar a Watsonx.");
      setAnalysisState('error');
    }
  };

  const handleSelectScenario = (sc) => {
    setSelectedScenarioId(sc.nombre);
    // Filtrar visualmente podria implicar pasar los top IDs a mapData. 
    // Por simplicidad en este MVP saltamos focus y mantenemos el core heatmap.
  };

  // Calcular metricas sumarizadas
  const zonesSummary = React.useMemo(() => {
    if (!analysisResult) return { verdes: 0, cautela: 0, descarte: 0 };
    const vs = analysisResult.viability_scores || [];
    return {
      verdes: vs.filter(v => v.clasificacion === 'Alta viabilidad').length,
      cautela: vs.filter(v => v.clasificacion === 'Viabilidad media').length,
      descarte: vs.filter(v => v.clasificacion === 'Descarte').length
    };
  }, [analysisResult]);

  // Si no hay análisis, forzamos usar el base geojson en el mapa como demand
  const effectiveDemandGeoJSON = analysisResult ? mapData.demandGeoJSON : baseGeoJSON;

  return (
    <div className="flex flex-col h-screen w-full bg-slate-950 font-sans text-slate-200 overflow-hidden">
      
      {/* ── BARRA SUPERIOR ── */}
      <header className="h-16 shrink-0 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6 z-[600] relative shadow-md">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 text-white p-1.5 rounded-lg shadow-[0_0_15px_rgba(79,70,229,0.5)]">
            <Layers size={22} />
          </div>
          <h1 className="text-2xl font-black tracking-tighter text-white">
            URBANIA<span className="text-indigo-400 font-light">.ai</span>
          </h1>
          <span className="ml-4 px-2 py-0.5 rounded border border-slate-700 bg-slate-800 text-xs font-mono text-slate-400">
            {analysisResult?.metadata?.sector || 'Selecciona un Sector'}
          </span>
        </div>
        
        <div className="flex items-center gap-4">
          {health.mock_mode && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-500 text-[10px] font-bold uppercase tracking-widest animate-pulse">
              <AlertTriangle size={14} /> Modo Demo / Fallback
            </span>
          )}
          <div className="w-8 h-8 rounded-full bg-indigo-900/50 flex items-center justify-center border border-indigo-500/30 font-bold text-xs text-indigo-300">
            C
          </div>
        </div>
      </header>

      {/* ── CONTENEDOR PRINCIPAL: PANELS + MAPA ── */}
      <div className="flex-1 flex overflow-hidden relative">
        
        {/* PANEL IZQUIERDO FIJO */}
        <aside className="w-[400px] shrink-0 bg-slate-950 border-r border-slate-800 flex flex-col z-[500] shadow-2xl overflow-y-auto overflow-x-hidden">
          <div className="p-5 flex-1 flex flex-col gap-6">
            <SectorSelector onAnalyze={handleAnalyze} isAnalyzing={analysisState === 'loading'} />
            
            {analysisState === 'complete' && (
              <div className="animate-in fade-in slide-in-from-left-4 duration-500 ease-out space-y-6">
                <div className="[&>div]:!grid-cols-1 [&>div]:!gap-3">
                   <MetricsPanel metadata={analysisResult.metadata} zonasSummary={zonesSummary} />
                </div>
                
                <div className="border-t border-slate-800 pt-5">
                   <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">Escenarios de Despliegue</h3>
                   <div className="[&>div]:!grid-cols-1 [&>div]:!gap-4">
                     <ScenariosPanel 
                       scenarios={analysisResult.scenarios} 
                       sector={analysisResult.metadata.sector}
                       selectedScenarioId={selectedScenarioId}
                       onSelectScenario={handleSelectScenario}
                     />
                   </div>
                </div>
              </div>
            )}
            
            {/* ESPACIO VACIO / MOCKUP INICIAL */}
            {analysisState === 'idle' && (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-slate-800 rounded-xl m-2 opacity-50">
                <Layers size={48} className="text-slate-600 mb-4" />
                <p className="text-slate-400 text-sm">Configura los parámetros estratégicos y presiona Analizar Zona para computar la viabilidad con Watsonx AI.</p>
              </div>
            )}
          </div>
        </aside>

        {/* CENTRO: MAPA LEAFLET */}
        <main className="flex-1 relative z-0 bg-slate-900">
          <UrbaniaMap 
             demandGeoJSON={effectiveDemandGeoJSON}
             riskGeoJSON={mapData.riskGeoJSON}
             viabilityScores={mapData.viabilityScores}
             activeLayer={activeLayer}
             onLayerChange={setActiveLayer}
             selectedZone={selectedZone}
             onZoneSelect={setSelectedZone}
          />

          {/* LOADING OVERLAY */}
          {analysisState === 'loading' && (
            <div className="absolute inset-0 z-[1000] bg-slate-950/80 backdrop-blur-sm flex flex-col items-center justify-center animate-in fade-in duration-300">
              <div className="bg-slate-900 border border-slate-700 rounded-2xl p-8 flex flex-col items-center shadow-2xl max-w-sm text-center">
                <div className="relative w-16 h-16 flex items-center justify-center mb-6">
                  <div className="absolute inset-0 border-4 border-indigo-500/30 rounded-full"></div>
                  <div className="absolute inset-0 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                  <Activity className="text-indigo-400 absolute" size={24} />
                </div>
                <h3 className="text-lg font-bold text-white mb-2">Computando IA Territorial</h3>
                <p className="text-sm text-slate-400">Procesando {baseGeoJSON?.features?.length || 50} manzanas geográficas cruzando Demanda, Riesgo y Watsonx...</p>
              </div>
            </div>
          )}
        </main>

        {/* PANEL DERECHO DESLIZABLE (EXECUTIVE REPORT) */}
        <aside 
          className={`absolute top-0 right-0 h-full w-[35%] min-w-[500px] bg-slate-900/95 backdrop-blur-xl border-l border-slate-700 z-[800] 
                      shadow-[0_0_50px_rgba(0,0,0,0.5)] transition-transform duration-500 ease-custom-cubic
                      ${analysisState === 'complete' ? 'translate-x-0' : 'translate-x-full'}`}
        >
          <div className="h-full overflow-y-auto p-4 md:p-8">
             <div className="flex justify-end mb-2">
                <button 
                  onClick={() => {/* Collapse handle opcional */}} 
                  className="p-1 hover:bg-slate-800 rounded text-slate-500 hover:text-white lg:hidden"
                >
                  <X size={24} />
                </button>
             </div>
             {analysisState === 'complete' && (
                <ExecutiveReportPanel 
                   report={analysisResult.executive_report} 
                   analysisId={analysisResult.analysis_id} 
                />
             )}
          </div>
        </aside>

      </div>

      {/* ERROR TOAST */}
      {analysisState === 'error' && (
        <div className="fixed bottom-6 right-6 z-[2000] bg-rose-600/90 backdrop-blur border border-rose-500 text-white p-4 rounded-xl shadow-2xl flex items-start gap-4 max-w-md animate-in slide-in-from-bottom-5">
           <AlertTriangle size={24} className="shrink-0 mt-0.5" />
           <div className="flex-1">
             <h4 className="font-bold mb-1">Error de Procesamiento</h4>
             <p className="text-sm text-rose-100">{errorMessage}</p>
           </div>
           <button onClick={() => setAnalysisState('idle')} className="p-1 hover:bg-rose-500 rounded">
             <X size={16} />
           </button>
        </div>
      )}

    </div>
  );
}
