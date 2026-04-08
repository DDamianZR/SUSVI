import React from 'react';
import { Map, ShieldCheck, AlertTriangle, AlertOctagon } from 'lucide-react';

export default function MetricsPanel({ metadata, zonasSummary }) {
  const total = metadata?.n_manzanas_analizadas || 0;
  const verdes = zonasSummary?.verdes || 0;
  const cautela = zonasSummary?.cautela || 0;
  const descarte = zonasSummary?.descarte || 0;

  const cards = [
    { title: 'Manzanas Analizadas', value: total, icon: Map, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
    { title: 'Zonas Verdes', value: verdes, icon: ShieldCheck, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
    { title: 'Zonas Cautela', value: cautela, icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
    { title: 'Zonas Descarte', value: descarte, icon: AlertOctagon, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 w-full">
      {cards.map((c, i) => {
        const Icon = c.icon;
        return (
          <div key={i} className={`flex items-center p-4 rounded-xl border ${c.bg} ${c.border} backdrop-blur-sm transition-all duration-300 hover:shadow-lg bg-slate-900/80`}>
            <div className={`p-3 rounded-lg ${c.bg} mr-4`}>
              <Icon size={24} className={c.color} />
            </div>
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">{c.title}</p>
              <p className={`text-2xl font-mono font-bold mt-1 ${c.color}`}>{c.value}</p>
            </div>
          </div>
        )
      })}
    </div>
  );
}
