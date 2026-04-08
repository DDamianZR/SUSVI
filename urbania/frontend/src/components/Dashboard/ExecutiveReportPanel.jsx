import React, { useState } from 'react';
import { FileText, Download, AlertCircle, ArrowRight, Lightbulb, Loader2, Database } from 'lucide-react';
import { api } from '../../services/api.js';

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export default function ExecutiveReportPanel({ report, analysisId }) {
  const [exportingGeo, setExportingGeo] = useState(false);
  const [exportingPDF, setExportingPDF] = useState(false);
  const [exportingRaw, setExportingRaw] = useState(false);

  if (!report) return null;

  const shortId = analysisId ? analysisId.substring(0, 8) : 'N/A';

  const handleExportGeoJSON = async () => {
    setExportingGeo(true);
    try {
      const blob = await api.exportGeoJSON(analysisId);
      downloadBlob(blob, `urbania_analysis_${shortId}.geojson`);
    } catch (e) {
      alert("Error en exportación GeoJSON: " + e.message);
    } finally {
      setExportingGeo(false);
    }
  };

  const handleExportPDF = async () => {
    setExportingPDF(true);
    try {
      const blob = await api.exportPDF(analysisId);
      downloadBlob(blob, `Reporte_Ejecutivo_${shortId}.pdf`);
    } catch (e) {
      alert("Error en exportación PDF: " + e.message);
    } finally {
      setExportingPDF(false);
    }
  };

  const handleExportRaw = async () => {
    setExportingRaw(true);
    try {
      const data = await api.exportRawData(analysisId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      downloadBlob(blob, `urbania_raw_data_${shortId}.json`);
    } catch (e) {
      // Si falla el endpoint raw-data, exportar el report completo como JSON
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      downloadBlob(blob, `urbania_report_data_${shortId}.json`);
    } finally {
      setExportingRaw(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 md:p-8 shadow-2xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4 border-b border-slate-800 pb-5">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <FileText className="text-indigo-400" />
            Reporte Ejecutivo C-Suite
          </h2>
          <p className="text-xs text-slate-400 mt-2 font-mono bg-slate-800 px-2 py-1 rounded inline-block">
            ID: {analysisId}
          </p>
          {report.source && (
            <span className={`ml-2 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest ${
              report.source === 'watsonx'
                ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
            }`}>
              {report.source === 'watsonx' ? '⚡ Watsonx AI' : '🔢 Algoritmo'}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleExportRaw}
            disabled={exportingRaw || !analysisId}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-2 rounded-lg text-xs font-semibold transition-colors disabled:opacity-40"
            title="Exportar datos crudos en JSON para interpretación futura"
          >
            {exportingRaw ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
            JSON Raw
          </button>
          <button
            onClick={handleExportGeoJSON}
            disabled={exportingGeo || !analysisId}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-40"
          >
            {exportingGeo ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
            GeoJSON
          </button>
          <button
            onClick={handleExportPDF}
            disabled={exportingPDF || !analysisId}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors shadow-lg shadow-indigo-500/20 disabled:opacity-40"
          >
            {exportingPDF ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
            Exportar PDF
          </button>
        </div>
      </div>

      <div className="space-y-10">
        {/* Resumen Ejecutivo */}
        <section>
          <h3 className="text-sm font-bold text-indigo-400 uppercase tracking-widest mb-3 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span> Resumen Ejecutivo
          </h3>
          <p className="text-slate-300 leading-relaxed text-sm whitespace-pre-line bg-slate-800/30 p-5 rounded-lg border border-slate-800">
            {report.resumen_ejecutivo}
          </p>
        </section>

        {/* Tabla Comparativa de Escenarios */}
        {report.escenarios && report.escenarios.length > 0 && (
          <section>
            <h3 className="text-sm font-bold text-indigo-400 uppercase tracking-widest mb-3 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span> Comparativa de Escenarios
            </h3>
            <div className="overflow-x-auto rounded-lg border border-slate-700">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-800 text-slate-300 text-xs uppercase font-semibold">
                    <th className="p-4 border-b border-slate-700">Escenario</th>
                    <th className="p-4 text-right border-b border-slate-700">ROI 5A</th>
                    <th className="p-4 text-right border-b border-slate-700">Payback</th>
                    <th className="p-4 text-right border-b border-slate-700">Exposición</th>
                    <th className="p-4 border-b border-slate-700 w-1/2">Narrativa</th>
                  </tr>
                </thead>
                <tbody className="text-sm text-slate-300 divide-y divide-slate-800/50">
                  {report.escenarios.map((esc, i) => (
                    <tr key={i} className={`hover:bg-slate-800/40 transition-colors ${esc.nombre?.toUpperCase() === 'EQUILIBRADO' ? 'bg-indigo-900/10' : ''}`}>
                      <td className="p-4 font-bold text-white whitespace-nowrap">{esc.nombre}</td>
                      <td className="p-4 text-right font-mono text-emerald-400 font-bold">
                        {typeof esc.roi === 'number' ? `${esc.roi.toFixed(1)}%` : `${esc.roi}%`}
                      </td>
                      <td className="p-4 text-right font-mono text-slate-400">
                        {typeof esc.payback === 'number' ? `${esc.payback.toFixed(1)}a` : `${esc.payback}a`}
                      </td>
                      <td className="p-4 text-right font-mono text-rose-400">
                        {typeof esc.exposicion === 'number' ? `${esc.exposicion.toFixed(1)}M` : `${esc.exposicion}M`}
                      </td>
                      <td className="p-4 text-xs leading-relaxed text-slate-400 italic">{esc.recomendacion_narrativa}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Recomendación Final */}
        {report.recomendacion_final && (
          <section>
            <div className="bg-indigo-900/20 border border-indigo-500/30 p-6 rounded-xl border-l-[6px] border-l-indigo-500 shadow-xl shadow-indigo-900/10">
              <h3 className="flex items-center gap-2 text-indigo-300 font-bold mb-3 uppercase tracking-wider text-sm">
                <Lightbulb size={20} className="text-indigo-400" /> Recomendación Estratégica
              </h3>
              <p className="text-white text-base leading-relaxed">{report.recomendacion_final}</p>
            </div>
          </section>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Advertencias */}
          {report.advertencias && report.advertencias.length > 0 && (
            <section>
              <h3 className="text-sm font-bold text-rose-400 uppercase tracking-widest mb-4 flex items-center gap-2 pb-2 border-b border-slate-800">
                <AlertCircle size={16} /> Alertas Estratégicas
              </h3>
              <ul className="space-y-3">
                {report.advertencias.map((adv, i) => (
                  <li key={i} className="flex gap-3 text-sm text-slate-300 bg-rose-950/20 p-3 rounded-lg border border-rose-900/30">
                    <div className="mt-1 w-2 h-2 bg-rose-500 rounded-full shrink-0 shadow-[0_0_8px_rgba(244,63,94,0.6)]" />
                    <span className="leading-relaxed">{adv}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Próximos Pasos */}
          {report.proximos_pasos && report.proximos_pasos.length > 0 && (
            <section>
              <h3 className="text-sm font-bold text-emerald-400 uppercase tracking-widest mb-4 flex items-center gap-2 pb-2 border-b border-slate-800">
                <ArrowRight size={16} /> Próximos Pasos
              </h3>
              <ol className="space-y-3 list-decimal list-inside text-sm text-slate-300">
                {report.proximos_pasos.map((paso, i) => (
                  <li key={i} className="p-3 bg-slate-800/30 rounded-lg border border-slate-700/50 leading-relaxed">
                    <span className="ml-2">{paso}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>

        {/* Nota de interpretación */}
        <div className="mt-4 p-4 bg-amber-950/20 border border-amber-800/30 rounded-lg">
          <p className="text-xs text-amber-400/80 flex items-start gap-2">
            <Database size={14} className="shrink-0 mt-0.5" />
            <span>
              <strong>Datos para interpretación:</strong> Esta demo expone los datos crudos completos 
              (scores, clasificaciones, factores de riesgo, justificaciones por zona) para su interpretación 
              en la capa de análisis posterior. Usa "JSON Raw" para descargar todos los datos sin procesar.
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
