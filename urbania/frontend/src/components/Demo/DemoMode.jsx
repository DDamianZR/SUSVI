import React, { useState } from 'react';
import { Zap, Wifi, DatabaseZap } from 'lucide-react';
import { api } from '../../services/api.js';

const DemoMode = ({ onInstantLoad, onLiveAnalyze, isRealtime, onToggleRealtime }) => {
  const [loading, setLoading] = useState(false);

  const handleInstantLoad = async () => {
    setLoading(true);
    try {
      const data = await api.getDemoResult();
      onInstantLoad(data);
    } catch {
      // Si no existe demo_result.json, disparar análisis completo con parámetros demo
      try {
        const data = await api.analyze('telecomunicaciones', {
          ticket_inversion_mxn: 2000000,
          vida_util_anios: 8,
          tasa_descuento: 0.12,
          n_unidades_objetivo: 12
        }, null);
        onInstantLoad(data);
      } catch (err) {
        alert("Error cargando demo: " + err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000] flex flex-col items-center pointer-events-none">
      {/* Banner */}
      <div className="pointer-events-auto bg-amber-500/90 text-amber-950 px-6 py-2 rounded-full font-bold shadow-lg shadow-amber-500/20 backdrop-blur-md border border-amber-400 flex items-center justify-center space-x-2 text-sm">
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-200 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-white"></span>
        </span>
        <span>MODO DEMO — Datos simulados · Zona Piloto CDMX</span>
      </div>

      {/* Controles */}
      <div className="pointer-events-auto mt-3 bg-slate-900/95 border border-slate-700/50 p-3 rounded-xl shadow-xl backdrop-blur flex items-center space-x-4 text-sm">

        {/* Toggle Demo / Realtime */}
        <div className="flex items-center space-x-2 text-slate-300">
          <DatabaseZap size={14} className={!isRealtime ? "text-amber-400" : "text-slate-500"} />
          <span className={`text-xs ${!isRealtime ? "text-amber-400 font-semibold" : "text-slate-500"}`}>Demo Seed</span>
          <button
            type="button"
            onClick={onToggleRealtime}
            className={`relative inline-flex h-5 w-10 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ${isRealtime ? 'bg-indigo-600' : 'bg-slate-600'}`}
          >
            <span aria-hidden="true" className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ${isRealtime ? 'translate-x-5' : 'translate-x-0'}`} />
          </button>
          <Wifi size={14} className={isRealtime ? "text-indigo-400" : "text-slate-500"} />
          <span className={`text-xs ${isRealtime ? "text-indigo-400 font-semibold" : "text-slate-500"}`}>API en vivo</span>
        </div>

        <div className="h-5 w-px bg-slate-700" />

        {/* Botón carga instantánea */}
        {!isRealtime && (
          <button
            onClick={handleInstantLoad}
            disabled={loading}
            className="flex items-center space-x-2 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white px-4 py-1.5 rounded-lg shadow-md transition-all disabled:opacity-50 disabled:cursor-not-allowed text-xs font-bold"
          >
            <Zap size={14} className={loading ? "animate-spin" : ""} />
            <span>{loading ? "Calculando…" : "⚡ Cargar Demo Instantáneo"}</span>
          </button>
        )}

        {isRealtime && (
          <span className="text-slate-400 italic text-xs">Usa el panel izquierdo para disparar análisis Watsonx</span>
        )}
      </div>
    </div>
  );
};

export default DemoMode;
