import React, { useState } from 'react';
import { Target, Shield, Building2, Wifi, Zap, Loader2 } from 'lucide-react';

export default function SectorSelector({ onAnalyze, isAnalyzing }) {
  const [sector, setSector] = useState('telecomunicaciones');
  const [params, setParams] = useState({
    ticket_inversion_mxn: 500000,
    n_unidades_objetivo: 10,
    vida_util_anios: 5,
    tasa_descuento: 0.12
  });

  const sectors = [
    { id: 'telecomunicaciones', label: 'Telecom', icon: Wifi },
    { id: 'seguridad', label: 'Seguridad', icon: Shield },
    { id: 'inmobiliario', label: 'Real Estate', icon: Building2 }
  ];

  const handleParamChange = (field, value) => {
    setParams(prev => ({ ...prev, [field]: Number(value) }));
  };

  const handleAnalyze = () => {
    onAnalyze(sector, params);
  };

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 md:p-6 shadow-2xl w-full">
      <h3 className="text-white font-bold mb-5 flex items-center gap-2 text-lg">
        <Target size={20} className="text-indigo-400" /> Configuración Estratégica
      </h3>

      {/* Selector de Sector */}
      <div className="mb-6">
        <label className="text-xs text-slate-400 uppercase tracking-widest font-semibold block mb-2">Industria Objetivo</label>
        <div className="flex gap-2 p-1.5 bg-slate-950 rounded-lg border border-slate-800">
          {sectors.map(s => {
            const Icon = s.icon;
            const isActive = sector === s.id;
            return (
              <button
                key={s.id}
                onClick={() => setSector(s.id)}
                className={`flex-1 py-2.5 px-2 rounded-md text-xs font-bold flex flex-col items-center gap-1.5 transition-all duration-200 ${
                  isActive 
                    ? 'bg-indigo-600 text-white shadow-md' 
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                <Icon size={18} /> {s.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Parametros Financieros */}
      <div className="space-y-6 bg-slate-800/30 p-4 rounded-xl border border-slate-800/80">
        <div>
          <div className="flex justify-between items-end mb-2">
            <label className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Ticket por Unidad</label>
            <span className="text-sm text-emerald-400 font-mono font-bold bg-emerald-950/30 px-2 rounded">
              ${params.ticket_inversion_mxn.toLocaleString()} MXN
            </span>
          </div>
          <input 
            type="range" min="100000" max="5000000" step="50000"
            value={params.ticket_inversion_mxn}
            onChange={(e) => handleParamChange('ticket_inversion_mxn', e.target.value)}
            className="w-full accent-indigo-500 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer"
          />
          <div className="flex justify-between mt-1 text-[10px] text-slate-500 font-mono">
            <span>$100K</span>
            <span>$5M</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-5">
          <div>
            <label className="block text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-2">Nº Unidades</label>
            <input 
              type="number" min="1" max="100"
              value={params.n_unidades_objetivo}
              onChange={(e) => handleParamChange('n_unidades_objetivo', e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-white font-mono text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all outline-none"
            />
          </div>
          <div>
            <label className="block text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-2">Vida Útil (Años)</label>
             <input 
              type="number" min="1" max="20"
              value={params.vida_util_anios}
              onChange={(e) => handleParamChange('vida_util_anios', e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-white font-mono text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all outline-none"
            />
          </div>
        </div>

        <div>
           <div className="flex justify-between items-end mb-2">
            <label className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Tasa Descuento WACC</label>
            <span className="text-sm text-indigo-300 font-mono font-bold bg-indigo-950/30 px-2 rounded">
              {(params.tasa_descuento * 100).toFixed(1)}%
            </span>
          </div>
          <input 
            type="range" min="0.05" max="0.25" step="0.01"
            value={params.tasa_descuento}
            onChange={(e) => handleParamChange('tasa_descuento', e.target.value)}
             className="w-full accent-indigo-500 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer"
          />
        </div>
      </div>

      <button 
        onClick={handleAnalyze}
        disabled={isAnalyzing}
        className="mt-8 w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 disabled:border overflow-hidden disabled:border-slate-700 text-white font-bold py-3.5 rounded-xl flex justify-center items-center gap-2 transition-all duration-300 shadow-lg shadow-indigo-600/20 active:scale-[0.98]"
      >
        {isAnalyzing ? (
          <><Loader2 className="animate-spin" size={18} /> Computando IA...</>
        ) : (
          <><Zap size={18} /> Iniciar Análisis Territorial</>
        )}
      </button>
    </div>
  );
}
