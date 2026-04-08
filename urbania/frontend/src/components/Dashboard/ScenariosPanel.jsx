import React from 'react';
import { TrendingUp, Shield, Scale, ChevronRight } from 'lucide-react';

const formatMXN = (val) => new Intl.NumberFormat('es-MX', { 
  style: 'currency', 
  currency: 'MXN', 
  maximumFractionDigits: 0 
}).format(val || 0);

export default function ScenariosPanel({ scenarios, sector, onSelectScenario, selectedScenarioId }) {
  if (!scenarios || scenarios.length === 0) return null;

  const getBadges = (name) => {
    switch (name?.toUpperCase()) {
      case 'AGRESIVO': return { icon: TrendingUp, color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30' };
      case 'CONSERVADOR': return { icon: Shield, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
      case 'EQUILIBRADO': return { icon: Scale, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/50' };
      default: return { icon: Scale, color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/30' };
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {scenarios.map((sc, i) => {
        const isEquilibrado = sc.nombre?.toUpperCase() === 'EQUILIBRADO';
        const st = getBadges(sc.nombre);
        const Icon = st.icon;
        const isSelected = selectedScenarioId === sc.nombre;

        return (
          <div 
            key={i} 
            className={`relative flex flex-col p-5 bg-slate-900 rounded-xl border-2 transition-all duration-300 ${
              isSelected 
                ? 'border-indigo-500 shadow-[0_0_20px_rgba(99,102,241,0.3)] scale-[1.02] z-10' 
                : isEquilibrado 
                  ? 'border-blue-500/50 shadow-lg' 
                  : 'border-slate-800'
            }`}
          >
            {isEquilibrado && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest shadow-md">
                Recomendado
              </div>
            )}
            
            <div className="flex justify-between items-start mb-5">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-lg ${st.bg}`}>
                  <Icon size={20} className={st.color} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white tracking-wide">{sc.nombre}</h3>
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider">{sector}</span>
                </div>
              </div>
            </div>

            <div className="space-y-4 flex-1">
              <div>
                <p className="text-xs text-slate-400 uppercase">ROI Estimado (5 años)</p>
                <div className="flex items-baseline gap-2 mt-1">
                  <span className="text-4xl font-mono font-bold text-white">{sc.roi_estimado_5_anios}%</span>
                  <TrendingUp size={14} className="text-emerald-400" />
                </div>
              </div>

              <div>
                <div className="flex justify-between mb-1.5">
                  <span className="text-xs text-slate-400 uppercase">Payback Period</span>
                  <span className="font-mono text-sm text-indigo-300 font-semibold">{sc.payback_period_anios} años</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                  <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${Math.min(100, (sc.payback_period_anios / 5) * 100)}%` }}></div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-800/50 grid grid-cols-2 gap-3">
                <div className="bg-slate-800/50 p-2 rounded-lg">
                   <p className="text-[10px] text-slate-400 uppercase mb-1">Max Riesgo</p>
                   <p className="font-mono text-sm text-rose-400">{formatMXN(sc.exposicion_max_riesgo_mxn)}</p>
                </div>
                <div className="bg-emerald-500/10 p-2 rounded-lg border border-emerald-500/20">
                   <p className="text-[10px] text-emerald-500 uppercase mb-1">Ahorro Est.</p>
                   <p className="font-mono text-sm text-emerald-400">{formatMXN(sc.perdidas_evitadas_vs_aleatorio_mxn)}</p>
                </div>
              </div>

              <div className="flex justify-between items-center bg-slate-800/30 p-2 rounded text-sm">
                <span className="text-slate-400">Zonas seleccionadas:</span>
                <span className="font-mono text-white bg-slate-800 px-2 rounded">{sc.zonas_seleccionadas?.length || 0}</span>
              </div>
            </div>

            <button 
              onClick={() => onSelectScenario(sc)}
              className={`mt-5 w-full py-3 rounded-lg flex items-center justify-center font-bold text-sm transition-all duration-200 ${
                isSelected 
                   ? 'bg-indigo-600 text-white shadow-lg' 
                   : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
               {isSelected ? 'Mostrando en Mapa' : 'Seleccionar Escenario'} 
               <ChevronRight size={18} className={`ml-1 transition-transform ${isSelected ? 'translate-x-1' : ''}`} />
            </button>
          </div>
        )
      })}
    </div>
  );
}
