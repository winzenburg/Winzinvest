'use client';

import React, { useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';

interface Recommendation {
  id: string;
  priority: 'critical' | 'warning' | 'opportunity' | 'info';
  category: string;
  title: string;
  detail: string;
  action: string;
  generated_at: string;
}

interface Greeks {
  net_theta: number;
  net_delta: number;
  net_gamma: number;
  net_vega: number;
  theta_monthly: number;
  theta_annual: number;
  theta_yield_pct: number;
  delta_pct_nlv: number;
  vega_pct_nlv: number;
  generated_at: string;
}

interface Scenario {
  scenario_id: string;
  label: string;
  color: string;
  total_pnl: number;
  pnl_pct: number;
  severity: string;
  action: string;
}

interface BulltardEntry {
  date: string;
  title: string;
  url: string;
  bias_score: number;
  bias_label: string;
  key_levels: string[];
  themes: string[];
  tickers_mentioned: string[];
  summary: string;
  pulled_at: string;
}

interface IntelligenceData {
  recommendations: {
    generated_at: string;
    summary: { critical: number; warning: number; opportunity: number; info: number; queued_trades: number };
    recommendations: Recommendation[];
  } | null;
  greeks: Greeks | null;
  scenarios: { scenarios: Scenario[]; worst_case: { label: string; pnl: number; pnl_pct: number } } | null;
}

const BIAS_STYLES: Record<string, { bg: string; border: string; badge: string; dot: string }> = {
  VERY_BEARISH: { bg: 'bg-red-50',    border: 'border-red-200',    badge: 'bg-red-600 text-white',     dot: 'bg-red-500' },
  BEARISH:      { bg: 'bg-orange-50', border: 'border-orange-200', badge: 'bg-orange-500 text-white',  dot: 'bg-orange-500' },
  NEUTRAL:      { bg: 'bg-slate-50',  border: 'border-slate-200',  badge: 'bg-slate-500 text-white',   dot: 'bg-slate-400' },
  BULLISH:      { bg: 'bg-emerald-50',border: 'border-emerald-200',badge: 'bg-emerald-600 text-white', dot: 'bg-emerald-500' },
  VERY_BULLISH: { bg: 'bg-emerald-50',border: 'border-emerald-300',badge: 'bg-emerald-700 text-white', dot: 'bg-emerald-600' },
};

function BulltardCard({ entry, history }: { entry: BulltardEntry; history: BulltardEntry[] }) {
  const [expanded, setExpanded] = useState(false);
  const style = BIAS_STYLES[entry.bias_label] ?? BIAS_STYLES.NEUTRAL;
  const biasEmoji: Record<string, string> = {
    VERY_BEARISH: '🔴', BEARISH: '🟠', NEUTRAL: '⚪', BULLISH: '🟢', VERY_BULLISH: '💚',
  };
  const emoji = biasEmoji[entry.bias_label] ?? '⚪';

  return (
    <div className={`rounded-xl border ${style.bg} ${style.border} p-4`}>
      <div className="flex items-start gap-3 mb-3">
        <div className="flex flex-col items-center gap-1 pt-0.5 shrink-0">
          <span className="text-lg leading-none">{emoji}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Bulltard Recap</span>
            <span className={`text-[11px] px-2 py-0.5 rounded-full font-bold uppercase ${style.badge}`}>
              {entry.bias_label.replace(/_/g, ' ')}
            </span>
            <span className="text-[11px] font-mono text-slate-500 tabular-nums">
              score {entry.bias_score > 0 ? '+' : ''}{entry.bias_score.toFixed(2)}
            </span>
          </div>
          <a
            href={entry.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-semibold text-slate-800 hover:text-sky-700 transition-colors"
          >
            {entry.title} ↗
          </a>
        </div>
      </div>

      {/* Themes */}
      {entry.themes.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {entry.themes.map((t) => (
            <span key={t} className="text-[11px] px-2 py-0.5 rounded-full bg-white/70 border border-slate-200 text-slate-700">
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Key levels */}
      {entry.key_levels.length > 0 && (
        <div className="mb-3 space-y-0.5">
          {entry.key_levels.slice(0, 3).map((lvl, i) => (
            <div key={i} className="text-xs text-slate-600 font-mono">• {lvl}</div>
          ))}
        </div>
      )}

      {/* Summary toggle */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-slate-500 hover:text-sky-600 transition-colors"
      >
        {expanded ? '▲ Less' : '▼ Read summary'}
      </button>
      {expanded && (
        <p className="mt-2 text-xs text-slate-600 leading-relaxed">{entry.summary}</p>
      )}

      {/* 7-day bias sparkline */}
      {history.length > 1 && (
        <div className="mt-3 pt-3 border-t border-current/10">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-1.5">7-day bias history</div>
          <div className="flex items-end gap-1 h-8">
            {history.slice(0, 7).reverse().map((h, i) => {
              const pct = Math.round(((h.bias_score + 1) / 2) * 100);
              const barH = Math.max(8, pct * 0.28);
              const barColor = h.bias_score <= -0.6 ? 'bg-red-400'
                : h.bias_score <= -0.25 ? 'bg-orange-400'
                : h.bias_score >= 0.25 ? 'bg-emerald-400'
                : 'bg-slate-300';
              return (
                <div
                  key={i}
                  title={`${h.date}: ${h.bias_label} (${h.bias_score > 0 ? '+' : ''}${h.bias_score.toFixed(2)})`}
                  className={`flex-1 rounded-sm ${barColor} opacity-80 hover:opacity-100 transition-opacity`}
                  style={{ height: `${barH}px` }}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

const PRIORITY_STYLES: Record<string, { bg: string; border: string; badge: string; title: string; detail: string; icon: string }> = {
  critical:    { bg: 'bg-red-50',     border: 'border-red-200',     badge: 'bg-red-600 text-white',          title: 'text-slate-900', detail: 'text-slate-600', icon: '🚨' },
  warning:     { bg: 'bg-amber-50',   border: 'border-amber-200',   badge: 'bg-amber-500 text-white',        title: 'text-slate-900', detail: 'text-slate-600', icon: '⚠️' },
  opportunity: { bg: 'bg-emerald-50', border: 'border-emerald-200', badge: 'bg-emerald-600 text-white',      title: 'text-slate-900', detail: 'text-slate-600', icon: '💡' },
  info:        { bg: 'bg-slate-50',   border: 'border-slate-200',   badge: 'bg-slate-600 text-white',        title: 'text-slate-900', detail: 'text-slate-600', icon: 'ℹ️' },
};

function GreeksCard({ greeks }: { greeks: Greeks }) {
  const theta    = greeks.net_theta;
  const delta    = greeks.net_delta;
  const deltaDir = delta >= 0 ? '+' : '';

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {[
        {
          label: 'Daily Theta',
          value: `$${Math.abs(theta).toFixed(0)}/day`,
          sub: `$${Math.abs(greeks.theta_monthly).toLocaleString('en-US', { maximumFractionDigits: 0 })}/mo`,
          color: theta >= 0 ? 'text-emerald-700' : 'text-red-600',
          tooltip: 'Options time decay collected per calendar day',
        },
        {
          label: 'Net Delta',
          value: `${deltaDir}$${Math.abs(delta).toFixed(0)}`,
          sub: `${deltaDir}${greeks.delta_pct_nlv.toFixed(1)}% of NLV`,
          color: Math.abs(greeks.delta_pct_nlv) > 20 ? 'text-amber-700' : 'text-slate-900',
          tooltip: 'Dollar exposure to a $1 move in the underlying',
        },
        {
          label: 'Theta Yield',
          value: `${greeks.theta_yield_pct.toFixed(1)}%`,
          sub: 'annualised',
          color: greeks.theta_yield_pct >= 20 ? 'text-emerald-700' : 'text-amber-700',
          tooltip: 'Annualised theta income as % of portfolio value',
        },
        {
          label: 'Net Vega',
          value: `$${greeks.net_vega.toFixed(0)}`,
          sub: 'per 1pt VIX',
          color: 'text-slate-900',
          tooltip: 'Portfolio $ change per 1-point VIX move',
        },
      ].map((m) => (
        <div key={m.label} className="rounded-lg bg-white border border-slate-200 p-3 card-elevated" title={m.tooltip}>
          <div className="text-xs font-medium text-slate-600 mb-1">{m.label}</div>
          <div className={`text-lg font-bold font-mono ${m.color}`}>{m.value}</div>
          <div className="text-xs text-slate-500 mt-0.5">{m.sub}</div>
        </div>
      ))}
    </div>
  );
}

function ScenarioBar({ scenario }: { scenario: Scenario }) {
  const pct      = scenario.pnl_pct;
  const barW     = Math.min(Math.abs(pct) * 3, 100);
  const isLoss   = pct < 0;
  const barColor = pct < -10 ? 'bg-red-500' : pct < -5 ? 'bg-amber-500' : pct < 0 ? 'bg-yellow-400' : 'bg-emerald-500';

  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="w-44 shrink-0 text-xs text-slate-700 truncate">{scenario.label}</div>
      <div className="flex-1 min-w-0 h-2 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-2 rounded-full ${barColor}`} style={{ width: `${barW}%` }} />
      </div>
      <div className={`w-28 shrink-0 text-right text-xs font-mono font-semibold leading-snug ${isLoss ? 'text-red-600' : 'text-emerald-700'}`}>
        <div>{isLoss ? '-' : '+'}${Math.abs(scenario.total_pnl).toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
        <div className="text-slate-500 font-normal">({pct.toFixed(1)}%)</div>
      </div>
    </div>
  );
}

export default function IntelligencePanel() {
  const [data, setData]             = useState<IntelligenceData | null>(null);
  const [loadError, setLoadError]   = useState<string | null>(null);
  const [expanded, setExpanded]     = useState<Set<string>>(new Set());
  const [showAll, setShowAll]       = useState(false);
  const [bulltard, setBulltard]     = useState<{ entries: BulltardEntry[]; latest: BulltardEntry | null } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetchWithAuth('/api/intelligence');
        if (!r.ok) {
          setLoadError('Could not load intelligence data');
          return;
        }
        setLoadError(null);
        setData((await r.json()) as IntelligenceData);
      } catch {
        setLoadError('Could not load intelligence data');
      }
    };
    void load();
    const t = setInterval(() => { void load(); }, 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const loadBulltard = async () => {
      try {
        const r = await fetchWithAuth('/api/bulltard');
        if (r.ok) setBulltard(await r.json());
      } catch {
        // non-critical — silently ignore
      }
    };
    void loadBulltard();
  }, []);

  if (loadError && !data) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {loadError}
      </div>
    );
  }

  if (!data) return null;

  const { recommendations: recData, greeks, scenarios } = data;
  const recs    = recData?.recommendations ?? [];
  const summary = recData?.summary;
  const visible = showAll ? recs : recs.filter((r) => r.priority !== 'info').slice(0, 8);

  const toggleExpand = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <div className="space-y-4">
      {/* Bulltard Recap Card — at top of intelligence panel */}
      {bulltard?.latest && (
        <BulltardCard entry={bulltard.latest} history={bulltard.entries} />
      )}

      {/* Header summary */}
      {summary && (
        <div className="flex flex-wrap gap-2 items-center">
          {summary.critical > 0 && (
            <span className="px-2 py-1 rounded text-xs font-bold bg-red-600 text-white">
              🚨 {summary.critical} Critical
            </span>
          )}
          {summary.warning > 0 && (
            <span className="px-2 py-1 rounded text-xs font-bold bg-amber-500 text-white">
              ⚠️ {summary.warning} Warning{summary.warning !== 1 ? 's' : ''}
            </span>
          )}
          {summary.opportunity > 0 && (
            <span className="px-2 py-1 rounded text-xs font-bold bg-emerald-600 text-white">
              💡 {summary.opportunity} Opportunit{summary.opportunity !== 1 ? 'ies' : 'y'}
            </span>
          )}
          {summary.queued_trades > 0 && (
            <span className="px-2 py-1 rounded text-xs font-bold bg-blue-600 text-white">
              📋 {summary.queued_trades} Trade{summary.queued_trades !== 1 ? 's' : ''} Queued
            </span>
          )}
          {recData?.generated_at && (
            <span className="ml-auto text-xs text-slate-500">
              Updated {new Date(recData.generated_at).toLocaleTimeString()}
            </span>
          )}
        </div>
      )}

      {/* Greeks */}
      {greeks && <GreeksCard greeks={greeks} />}

      {/* Scenario bars */}
      {scenarios && scenarios.scenarios.length > 0 && (
        <div className="rounded-lg bg-white border border-slate-200 p-4 card-elevated">
          <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">
            Stress Scenarios
          </div>
          <div className="space-y-0.5">
            {scenarios.scenarios.map((s) => (
              <ScenarioBar key={s.scenario_id} scenario={s} />
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {visible.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
            Recommendations
          </div>
          {visible.map((rec) => {
            const style  = PRIORITY_STYLES[rec.priority] ?? PRIORITY_STYLES.info;
            const isOpen = expanded.has(rec.id);
            return (
              <div
                key={rec.id}
                className={`rounded-lg border p-3 cursor-pointer transition-colors hover:brightness-95 ${style.bg} ${style.border}`}
                onClick={() => toggleExpand(rec.id)}
              >
                <div className="flex items-start gap-2">
                  <span className="text-base leading-none mt-0.5">{style.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-semibold uppercase ${style.badge}`}>
                        {rec.category}
                      </span>
                      {rec.action === 'execute' && (
                        <span className="text-xs px-1.5 py-0.5 rounded font-semibold bg-blue-600 text-white uppercase">
                          queued
                        </span>
                      )}
                      <span className={`text-sm font-medium ${style.title}`}>{rec.title}</span>
                    </div>
                    {isOpen && (
                      <p className={`mt-2 text-xs leading-relaxed ${style.detail}`}>{rec.detail}</p>
                    )}
                  </div>
                  <span className="text-slate-400 text-xs ml-1 shrink-0">{isOpen ? '▲' : '▼'}</span>
                </div>
              </div>
            );
          })}
          {recs.length > visible.length && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="w-full text-xs text-slate-600 hover:text-sky-600 font-medium py-1 transition-colors"
            >
              + {recs.length - visible.length} more (info)
            </button>
          )}
        </div>
      )}

      {recs.length === 0 && (
        <div className="text-center py-6 text-slate-600 text-sm">
          ✅ No active recommendations — portfolio looks clean.
        </div>
      )}
    </div>
  );
}
