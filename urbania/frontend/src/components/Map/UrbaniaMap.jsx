import React, { useMemo } from 'react';
import { MapContainer, TileLayer, GeoJSON, Popup } from 'react-leaflet';
import { AlertTriangle, CheckCircle, ChevronRight, X, BarChart3, Layers } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

// --- STYLING & COLORS ---
const COLORS = {
  risk: { VERDE: '#22c55e', CAUTELA: '#f59e0b', DESCARTE: '#ef4444' },
  viability: { 'Alta viabilidad': '#10b981', 'Viabilidad media': '#6366f1', 'Descarte': '#ef4444' }
};

const getFeatureStyle = (feature, activeLayer) => {
  const props = feature.properties;
  
  if (activeLayer === 'demand') {
    const score = props.score_demanda || 0;
    return {
      fillColor: '#3b82f6',
      fillOpacity: 0.2 + (score / 100) * 0.6,
      weight: 1,
      color: '#0f172a'
    };
  }
  
  if (activeLayer === 'risk') {
    const cat = props.clasificacion || 'VERDE';
    return {
      fillColor: COLORS.risk[cat] || '#22c55e',
      fillOpacity: 0.6,
      weight: 1,
      color: '#0f172a'
    };
  }
  
  if (activeLayer === 'viability') {
    const cat = props.clasificacion_viabilidad || 'Descarte';
    return {
      fillColor: COLORS.viability[cat] || '#ef4444',
      fillOpacity: 0.6,
      weight: 1,
      color: '#0f172a'
    };
  }

  return { fillOpacity: 0 };
};

// --- SUB-COMPONENTS ---

function ProgressBar({ progress, colorClass }) {
  return (
    <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1 overflow-hidden">
      <div className={`h-1.5 rounded-full ${colorClass}`} style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
    </div>
  );
}

function ZonePopupContent({ feature, onSeeMore }) {
  const props = feature.properties;
  const name = props.nombre || props.id || 'Zona Desconocida';
  
  const scoreDemanda = props.score_demanda || 0;
  const scoreRiesgo = props.score_riesgo || 0;
  const scoreViabilidad = props.score_viabilidad || 0;
  
  const riskColor = props.clasificacion === 'DESCARTE' ? 'bg-red-500' : (props.clasificacion === 'CAUTELA' ? 'bg-amber-500' : 'bg-emerald-500');
  const viaColor = props.clasificacion_viabilidad === 'Descarte' ? 'text-red-500' : (props.clasificacion_viabilidad === 'Viabilidad media' ? 'text-indigo-400' : 'text-emerald-500');

  return (
    <div className="p-3 bg-slate-900 text-slate-200 rounded-lg min-w-[240px] shadow-2xl border border-slate-700 font-sans">
      <h3 className="font-bold text-base mb-3 text-white border-b border-slate-700 pb-2">{name}</h3>
      
      <div className="space-y-3 mb-4 text-xs font-mono">
        <div>
          <div className="flex justify-between mb-0.5">
            <span className="text-slate-400">Demanda</span>
            <span className="font-bold text-blue-400">{scoreDemanda.toFixed(1)}</span>
          </div>
          <ProgressBar progress={scoreDemanda} colorClass="bg-blue-500" />
        </div>
        
        <div>
          <div className="flex justify-between mb-0.5">
            <span className="text-slate-400">Riesgo</span>
            <span className="font-bold" style={{ color: COLORS.risk[props.clasificacion] || '#fff' }}>
              {scoreRiesgo.toFixed(1)}
            </span>
          </div>
          <ProgressBar progress={scoreRiesgo} colorClass={riskColor} />
        </div>

        <div className="pt-2 mt-2 border-t border-slate-800 flex items-center justify-between">
          <span className="text-slate-400 uppercase tracking-widest text-[10px]">Viabilidad</span>
          <span className={`text-2xl font-black ${viaColor}`}>{scoreViabilidad.toFixed(1)}</span>
        </div>
      </div>

      <button 
        onClick={(e) => { e.stopPropagation(); onSeeMore(); }}
        className="w-full mt-2 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-semibold text-xs flex justify-center items-center transition-colors"
      >
        Ver análisis completo <ChevronRight size={14} className="ml-1" />
      </button>
    </div>
  );
}

function LayerControls({ activeLayer, onLayerChange, features }) {
  const counts = useMemo(() => {
    const res = { demandAlta: 0, riskDesc: 0, viaAlta: 0 };
    if (!features) return res;
    
    features.forEach(f => {
      const p = f.properties;
      if (p.score_demanda > 70) res.demandAlta++;
      if (p.clasificacion === 'DESCARTE') res.riskDesc++;
      if (p.clasificacion_viabilidad === 'Alta viabilidad') res.viaAlta++;
    });
    return res;
  }, [features]);

  const layers = [
    { id: 'demand', icon: BarChart3, label: 'Demanda',  badge: counts.demandAlta,  badgeColor: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    { id: 'risk',   icon: AlertTriangle, label: 'Riesgo',   badge: counts.riskDesc,   badgeColor: 'bg-red-500/20 text-red-400 border-red-500/30' },
    { id: 'viability', icon: CheckCircle, label: 'Viabilidad', badge: counts.viaAlta, badgeColor: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'}
  ];

  return (
    <div className="absolute top-4 right-4 z-[400] flex flex-col gap-2 bg-slate-900/40 p-2 rounded-xl backdrop-blur-md border border-slate-700/50">
      {layers.map(l => {
        const Icon = l.icon;
        const isActive = activeLayer === l.id;
        return (
          <button
            key={l.id}
            onClick={() => onLayerChange(l.id)}
            className={`flex items-center justify-between w-48 p-2.5 rounded-lg transition-all duration-200 border ${
              isActive 
                ? 'bg-slate-800 border-slate-600 shadow-lg' 
                : 'bg-slate-900/50 border-transparent hover:bg-slate-800/80 text-slate-400'
            }`}
          >
            <div className={`flex items-center gap-2 ${isActive ? 'text-white' : ''}`}>
              <Icon size={16} />
              <span className="text-sm font-semibold">{l.label}</span>
            </div>
            <div className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${isActive ? l.badgeColor : 'border-transparent text-slate-500'}`}>
              {l.badge}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function ZoneSidePanel({ zone, onClose }) {
  if (!zone) return null;
  const p = zone.properties;

  return (
    <div className="h-full flex flex-col pt-4 overflow-y-auto">
      <div className="flex justify-between items-start px-5 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white mb-1">{p.nombre || p.id}</h2>
          <span className="text-xs font-mono tracking-wider py-0.5 px-2 rounded-full border border-slate-700 text-slate-400 bg-slate-800/50">
            ID: {p.id}
          </span>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition-colors">
          <X size={20} />
        </button>
      </div>

      <div className="flex-1 p-5 space-y-6">
        {/* Metric Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
            <span className="text-[10px] uppercase text-slate-400">Score Demanda</span>
            <div className="text-xl font-mono text-blue-400 mt-1">{p.score_demanda?.toFixed(1) || '0.0'}</div>
          </div>
          <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
            <span className="text-[10px] uppercase text-slate-400">Score Viabilidad</span>
            <div className="text-xl font-mono text-emerald-400 mt-1">{p.score_viabilidad?.toFixed(1) || '0.0'}</div>
          </div>
        </div>

        {/* Riesgo Info */}
        <div className="space-y-3">
          <h4 className="text-sm font-bold text-white flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-500" /> Factores de Riesgo
          </h4>
          {p.factores_riesgo && p.factores_riesgo.length > 0 ? (
            <ul className="space-y-2">
              {p.factores_riesgo.map((f, i) => (
                <li key={i} className="text-xs bg-slate-800 p-2.5 rounded border border-slate-700/50 flex flex-col gap-1">
                  <span className="text-slate-300">{f.factor}</span>
                  <span className="text-[10px] text-amber-500/80 font-mono">Peso: {f.peso_relativo}</span>
                </li>
              ))}
            </ul>
          ) : (
             <p className="text-xs text-slate-500 italic">No hay factores de riesgo destacados.</p>
          )}
        </div>

        {/* Recomendaciones Mitigacion */}
        {p.recomendaciones_mitigacion && p.recomendaciones_mitigacion.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <CheckCircle size={16} className="text-emerald-500" /> Mitigación Sugerida
            </h4>
            <ul className="space-y-2">
              {p.recomendaciones_mitigacion.map((rec, i) => (
                <li key={i} className="text-xs text-slate-300 pl-3 relative before:content-[''] before:absolute before:left-0 before:top-1.5 before:w-1.5 before:h-1.5 before:bg-emerald-500 before:rounded-full">
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Razon de Descarte (si aplica) */}
        {p.razon_descarte && (
          <div className="mt-4 p-3 bg-red-950/30 border border-red-900/50 rounded-lg">
             <h4 className="text-xs font-bold text-red-400 uppercase tracking-wider mb-2">Motivo de Descarte</h4>
             <p className="text-xs text-slate-300 leading-relaxed">{p.razon_descarte}</p>
          </div>
        )}
      </div>
    </div>
  );
}


// --- MAIN MAP COMPONENT ---

export default function UrbaniaMap({ 
  demandGeoJSON, 
  riskGeoJSON, 
  viabilityScores, 
  activeLayer = 'viability',
  onLayerChange,
  onZoneSelect,
  selectedZone
}) {
  
  // 1. Unificar geometrías y propiedades en memorización rápida
  const unifiedFeatures = useMemo(() => {
    if (!demandGeoJSON || !demandGeoJSON.features) return null;
    
    // Diccionarios Rapidos O(1)
    const riskMap = {};
    if (riskGeoJSON && riskGeoJSON.features) {
      riskGeoJSON.features.forEach(f => {
        const id = f.properties?.id || f.id;
        riskMap[id] = f.properties;
      });
    }

    const viabilityMap = {};
    if (viabilityScores) {
      viabilityScores.forEach(v => {
        viabilityMap[v.id] = v;
      });
    }

    // Merge inyectado directo al feature.properties original (DemandGeo)
    const combined = {
      type: "FeatureCollection",
      features: demandGeoJSON.features.map(f => {
        const id = f.properties?.id || f.id;
        return {
          ...f,
          properties: {
             ...f.properties, // Incluye score_demanda
             ...riskMap[id],  // Cae encima con score_riesgo etc
             score_viabilidad: viabilityMap[id]?.score_viabilidad || 0,
             clasificacion_viabilidad: viabilityMap[id]?.clasificacion || 'Descarte'
          }
        };
      })
    };
    return combined;
  }, [demandGeoJSON, riskGeoJSON, viabilityScores]);


  return (
    <div className="relative w-full h-full flex overflow-hidden bg-slate-950 font-sans">
      
      {/* MAP LAYER */}
      <div className="flex-1 relative z-0">
        <MapContainer
          center={[19.4326, -99.1332]} // CDMX default
          zoom={12}
          zoomControl={false} // Para no estorbar nuestros paneles superpuestos, usualmente movemos zoom position
          className="w-full h-full bg-slate-900"
        >
          {/* Tiles - CartoDB Dark Matter */}
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
          />
          
          {/* Renderizado de Poligonos */}
          {unifiedFeatures?.features.map((feat, i) => (
            <GeoJSON
              key={`${feat.properties.id || i}-${activeLayer}`} // Fuerza Re-Render cuando cambia layer
              data={feat}
              style={() => getFeatureStyle(feat, activeLayer)}
            >
              {/* Leaftlet Native Popup pero inyectando Componentes de React adentro */}
              <Popup className="urbania-custom-popup bg-transparent border-0" closeButton={false}>
                <ZonePopupContent feature={feat} onSeeMore={() => onZoneSelect(feat)} />
              </Popup>
            </GeoJSON>
          ))}
        </MapContainer>

        {/* CUSTOM LAYER CONTROLS */}
        <LayerControls 
          activeLayer={activeLayer} 
          onLayerChange={onLayerChange} 
          features={unifiedFeatures?.features} 
        />
      </div>

      {/* FLY-OUT RIGHT SIDEBAR */}
      <div 
        className={`absolute top-0 right-0 h-full w-[320px] bg-slate-900 border-l border-slate-700 z-[500] 
                    shadow-2xl transition-transform duration-300 ease-custom-cubic
                    ${selectedZone ? 'translate-x-0' : 'translate-x-full'}`}
      >
        <ZoneSidePanel zone={selectedZone} onClose={() => onZoneSelect(null)} />
      </div>

      {/* CSS para limpiar el popup nativo de Leaflet y dejar a react estilizar TODO */}
      <style>{`
        .urbania-custom-popup .leaflet-popup-content-wrapper {
          background: transparent;
          box-shadow: none;
          padding: 0;
        }
        .urbania-custom-popup .leaflet-popup-tip {
          background: #0f172a; /* slate-900 */
          border: 1px solid #334155; /* slate-700 */
        }
        .ease-custom-cubic {
          transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
        }
      `}</style>
    </div>
  );
}
