import React, { useState } from 'react';

const DemoMode = ({ onInstantLoad, isRealtime, onToggleRealtime }) => {
  const [loading, setLoading] = useState(false);

  const handleInstantLoad = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/v1/demo-result');
      if (!res.ok) throw new Error("No se pudo cargar la demo cache");
      const data = await res.json();
      onInstantLoad(data);
    } catch (error) {
      alert("Error cargando demo instantáneo. ¿Ejecutaste demo_seed.py primero?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000] flex flex-col items-center">
      {/* Banner central */}
      <div className="bg-amber-500/90 text-amber-950 px-6 py-2 rounded-full font-bold shadow-lg shadow-amber-500/20 backdrop-blur-md border border-amber-400 flex items-center justify-center space-x-2 text-sm">
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-200 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-white"></span>
        </span>
        <span>MODO DEMO — Datos simulados de Zona Piloto CDMX</span>
      </div>

      {/* Controles del demo */}
      <div className="mt-3 bg-slate-900/90 border border-slate-700/50 p-3 rounded-xl shadow-xl backdrop-blur flex items-center space-x-6 text-sm">
        
        {/* Toggle Realtime vs Instant */}
        <div className="flex items-center space-x-3 text-slate-300">
          <span className={!isRealtime ? "text-amber-400 font-semibold" : "opacity-60"}>Demo Seed</span>
          <button 
            type="button"
            onClick={onToggleRealtime}
            className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${isRealtime ? 'bg-indigo-600' : 'bg-slate-600'}`}
          >
            <span aria-hidden="true" className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isRealtime ? 'translate-x-5' : 'translate-x-0'}`} />
          </button>
          <span className={isRealtime ? "text-indigo-400 font-semibold" : "opacity-60"}>Watsonx API</span>
        </div>

        {/* Separator */}
        <div className="h-6 w-px bg-slate-700"></div>

        {/* Boton cargar instantaneo (visible solo si no es realtime) */}
        {!isRealtime && (
          <button 
            onClick={handleInstantLoad}
            disabled={loading}
            className="flex items-center space-x-2 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white px-4 py-1.5 rounded-lg shadow-md transition-all disabled:opacity-50"
          >
            <span>{loading ? "Cargando..." : "⚡ Cargar Seed Instantáneo"}</span>
          </button>
        )}
        
        {isRealtime && (
          <span className="text-slate-400 italic">Dispara el panel izquierdo para IA</span>
        )}
      </div>
    </div>
  );
};

export default DemoMode;
