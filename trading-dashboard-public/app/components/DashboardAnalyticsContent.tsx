'use client';

import React from 'react';
import type { AnalyticsData } from '../api/analytics/route';
import type { StrategyAttribution } from '../api/strategy-attribution/route';
import Tooltip from './Tooltip';

function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return '—';
  return n.toFixed(decimals);
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n.toFixed(1)}%`;
}

function fmtPnl(n: number | null | undefined): string {
  if (n == null) return '—';
  const abs = Math.abs(n).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
  return n >= 0 ? abs : `(${abs.slice(1)})`;
}

function rColor(r: number | null | undefined): string {
  if (r == null) return 'text-stone-500';
  if (r >= 2) return 'text-emerald-600 font-semibold';
  if (r > 0) return 'text-emerald-500';
  if (r === 0) return 'text-stone-500';
  if (r > -1) return 'text-amber-600';
  return 'text-red-600';
}

function wrColor(wr: number | null | undefined): string {
  if (wr == null) return 'text-stone-500';
  if (wr >= 55) return 'text-emerald-600 font-semibold';
  if (wr >= 45) return 'text-sky-600';
  if (wr >= 35) return 'text-amber-600';
  return 'text-red-600';
}

function TipLabel({
  children,
  tip,
  placement = 'above',
}: {
  children: React.ReactNode;
  tip: string;
  placement?: 'above' | 'below';
}) {
  return (
    <Tooltip text={tip} placement={placement}>
      <span className="underline decoration-dotted decoration-stone-300 underline-offset-2 cursor-help">
        {children}
      </span>
    </Tooltip>
  );
}

function StatCard({
  label,
  value,
  sub,
  tooltip,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  tooltip?: string;
}) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-1">
        {tooltip ? <TipLabel tip={tooltip}>{label}</TipLabel> : label}
      </p>
      <p className="text-2xl font-serif font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-stone-500 mt-1">{sub}</p>}
    </div>
  );
}

function SectionTitle({ children, tooltip }: { children: React.ReactNode; tooltip?: string }) {
  return (
    <h2 className="text-lg font-serif font-bold text-slate-900 mb-3">
      {tooltip ? <TipLabel tip={tooltip}>{children}</TipLabel> : children}
    </h2>
  );
}

function GroupTable({
  rows,
  valueLabel = 'Avg R',
  valueTip = 'Average R-multiple — reward as a multiple of initial risk per trade. Above 0.5R is generally positive; above 1.0R is strong.',
}: {
  rows: AnalyticsData['by_strategy'];
  valueLabel?: string;
  valueTip?: string;
}) {
  if (!rows?.length) return <p className="text-sm text-stone-400">No data yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-stone-200 text-xs uppercase tracking-wider text-stone-500">
            <th className="text-left py-2 pr-4">
              <TipLabel tip="Strategy name or market regime label for this row">Label</TipLabel>
            </th>
            <th className="text-right py-2 pr-4">
              <TipLabel tip="Number of closed trades in this group">Trades</TipLabel>
            </th>
            <th className="text-right py-2 pr-4">
              <TipLabel tip="Percentage of trades in this group that closed with a positive P&L. Trend-following at 2:1 R:R can be profitable at 40–50%.">
                Win Rate
              </TipLabel>
            </th>
            <th className="text-right py-2 pr-4">
              <TipLabel tip={valueTip}>{valueLabel}</TipLabel>
            </th>
            <th className="text-right py-2">
              <TipLabel tip="Total realized P&L from all closed trades in this group. Unrealized gains/losses are excluded.">
                PnL
              </TipLabel>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-b border-stone-100 last:border-0">
              <td className="py-2 pr-4 font-medium text-slate-700">{r.label}</td>
              <td className="py-2 pr-4 text-right text-stone-600">{r.count}</td>
              <td className={`py-2 pr-4 text-right ${wrColor(r.win_rate_pct)}`}>{fmtPct(r.win_rate_pct)}</td>
              <td className={`py-2 pr-4 text-right ${rColor(r.avg_r_multiple)}`}>{fmt(r.avg_r_multiple, 2)}R</td>
              <td
                className={`py-2 text-right ${
                  r.total_pnl != null && r.total_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'
                }`}
              >
                {fmtPnl(r.total_pnl)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ACTION_COLORS: Record<string, string> = {
  SCALE_UP: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  REDUCE: 'bg-amber-100  text-amber-800  border-amber-300',
  PAUSE: 'bg-red-100    text-red-800    border-red-300',
  HOLD: 'bg-stone-100  text-stone-600  border-stone-300',
};

const ACTION_TIPS: Record<string, string> = {
  SCALE_UP:
    'Profit factor ≥1.5 and positive expectancy — this strategy has a demonstrated edge. Increase position sizing or allocation.',
  REDUCE: 'Marginal edge (profit factor 1.0–1.5). Trim position sizing for this strategy until performance improves.',
  PAUSE:
    'Profit factor <1.0 or negative expectancy — no statistical edge detected. Stop new entries for this strategy. Review parameters before resuming.',
  HOLD: 'Adequate performance — maintain current sizing and allocation. No change needed.',
};

const VALID_ATTRIBUTION_ACTIONS = ['SCALE_UP', 'REDUCE', 'PAUSE', 'HOLD'] as const;
type AttributionAction = (typeof VALID_ATTRIBUTION_ACTIONS)[number];

function normalizeAttributionAction(raw: unknown): AttributionAction {
  if (typeof raw !== 'string' || raw.length === 0) return 'HOLD';
  const upper = raw.toUpperCase().replace(/\s+/g, '_');
  if ((VALID_ATTRIBUTION_ACTIONS as readonly string[]).includes(upper)) {
    return upper as AttributionAction;
  }
  return 'HOLD';
}

const ATTRIBUTION_SECTION_TOOLTIP =
  'Generated every Friday. Includes profit factor, expectancy, and win rate per strategy and per strategy×regime. Also tracks P90 MFE per strategy for take-profit calibration, systematic vs. manual exit comparison, and strategy diversity (flags if one strategy is >55% of active trades). Recommendations feed the adaptive parameter engine.';

export default function DashboardAnalyticsContent({
  data,
  attribution,
  loading,
  error,
}: {
  data: AnalyticsData | null;
  attribution: StrategyAttribution | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <div className="py-16 text-center text-stone-500 text-sm" role="status">
        Loading trade analytics…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">
        {error ?? 'Analytics unavailable.'}
      </div>
    );
  }

  const { summary, by_strategy, by_regime, hold_time, exit_reasons, monthly_pnl, top_trades, conviction_vs_r } = data;
  const noTrades = !summary || summary.total_closed === 0;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-serif font-bold text-slate-900">Trade analytics</h2>
        <p className="text-xs text-stone-500 mt-1">
          {data.generated_at
            ? `Updated ${new Date(data.generated_at).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}`
            : 'Snapshot timing unavailable'}
        </p>
      </div>

      {(data.note || noTrades) && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-sm text-amber-800">
          {data.note ?? 'No closed trades yet. Analytics will populate as trades complete.'}
        </div>
      )}

      {!noTrades && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Closed Trades"
              value={summary.total_closed}
              sub={`${summary.wins ?? 0}W / ${summary.losses ?? 0}L / ${summary.breakeven ?? 0}B`}
              tooltip="Total positions fully exited (entry filled + exit filled). Open positions are not counted until they close."
            />
            <StatCard
              label="Win Rate"
              value={<span className={wrColor(summary.win_rate_pct)}>{fmtPct(summary.win_rate_pct)}</span>}
              sub="on closed positions"
              tooltip="Percentage of closed trades with a positive realized P&L. For trend-following strategies with 2:1+ R:R, a 40–50% win rate is typically sufficient to be profitable overall."
            />
            <StatCard
              label="Avg R-Multiple"
              value={<span className={rColor(summary.avg_r_multiple)}>{fmt(summary.avg_r_multiple, 2)}R</span>}
              sub="expectancy per trade"
              tooltip="Average reward expressed as a multiple of the initial risk (stop-loss distance). R=1.0 means you made exactly what you risked. R=2.0 means 2× your risk. Target: above 0.5R on average across all closed trades."
            />
            <StatCard
              label="Total PnL"
              value={
                <span
                  className={
                    summary.total_realized_pnl != null && summary.total_realized_pnl >= 0
                      ? 'text-emerald-600'
                      : 'text-red-600'
                  }
                >
                  {fmtPnl(summary.total_realized_pnl)}
                </span>
              }
              sub="realized only"
              tooltip="Sum of all realized gains and losses on closed positions. Unrealized P&L on open positions is excluded until they close."
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <SectionTitle tooltip="P&L broken down by trading strategy. Identifies which sub-strategies are contributing and which are underperforming. Feeds into Friday attribution recommendations.">
                Performance by Strategy
              </SectionTitle>
              <GroupTable rows={by_strategy} valueLabel="Avg R" />
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <SectionTitle tooltip="Same metrics grouped by the L1 execution regime active when each trade was entered. Reveals whether a weak strategy is failing in its target regime or being deployed in the wrong environment.">
                Performance by Regime at Entry
              </SectionTitle>
              <GroupTable rows={by_regime} valueLabel="Avg R" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <SectionTitle tooltip="Average calendar days from entry to exit for winning vs losing trades. Winners held longer than losers = letting profits run. If losers linger longer, consider tighter time stops on underperforming positions.">
                Hold Time: Winners vs Losers
              </SectionTitle>
              {hold_time ? (
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between py-2 border-b border-stone-100">
                    <span className="text-stone-500">
                      <TipLabel tip="Average calendar days from entry to exit for trades that closed with a positive P&L.">
                        Avg hold — winners
                      </TipLabel>
                    </span>
                    <span className="font-medium text-emerald-600">
                      {hold_time.avg_hold_days_winners != null ? `${fmt(hold_time.avg_hold_days_winners, 1)} days` : '—'}
                      <span className="text-stone-400 font-normal ml-1">({hold_time.winner_count} trades)</span>
                    </span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-stone-500">
                      <TipLabel tip="Average calendar days from entry to exit for trades that closed with a negative P&L. If higher than winners, losers are being held too long — tighten time stops.">
                        Avg hold — losers
                      </TipLabel>
                    </span>
                    <span className="font-medium text-red-600">
                      {hold_time.avg_hold_days_losers != null ? `${fmt(hold_time.avg_hold_days_losers, 1)} days` : '—'}
                      <span className="text-stone-400 font-normal ml-1">({hold_time.loser_count} trades)</span>
                    </span>
                  </div>
                  {hold_time.avg_hold_days_winners != null && hold_time.avg_hold_days_losers != null && (
                    <p className="text-xs text-stone-400 pt-2">
                      {hold_time.avg_hold_days_winners < hold_time.avg_hold_days_losers
                        ? 'Winners close faster than losers — consider tighter time stops on losing positions'
                        : 'Winners held longer than losers — consistent with letting profits run'}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-stone-400">No data yet.</p>
              )}
            </div>

            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <SectionTitle tooltip="How positions are actually exiting: TRAIL_HIT (IB trailing stop — primary exit for winners), STOP_HIT (hard stop), PROFIT_ROLL (options 80% decay), TIME_STOP (20-day cap), BOBBLEHEAD_EXIT (closed early after 2 days with no confirmation), MANUAL (discretionary override). Trailing stop should dominate winning exits; hard stop should dominate losers. High BOBBLEHEAD_EXIT rate means entry quality may be declining or execution is too early in the setup. High MANUAL rate is tracked separately to compare vs systematic exits.">
                Exit Reason Distribution
              </SectionTitle>
              {exit_reasons?.length ? (
                <div className="space-y-2">
                  {exit_reasons.map((e) => (
                    <div key={e.reason} className="flex items-center gap-3">
                      <div className="w-28 text-xs text-stone-600 shrink-0">{e.reason.replace('_', ' ')}</div>
                      <div className="flex-1 bg-stone-100 rounded-full h-2">
                        <div className="bg-slate-600 h-2 rounded-full" style={{ width: `${e.pct}%` }} />
                      </div>
                      <div className="text-xs text-stone-500 w-16 text-right">
                        {e.count} ({e.pct}%)
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-stone-400">No data yet.</p>
              )}
            </div>
          </div>

          {monthly_pnl && monthly_pnl.length > 0 && (
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <SectionTitle tooltip="Month-by-month realized P&L from closed positions only. Open positions are excluded until they close. Useful for spotting seasonal patterns or strategy regime sensitivity across market cycles.">
                Monthly Realized PnL
              </SectionTitle>
              <div className="flex items-end gap-2 h-32 mt-4">
                {monthly_pnl.map((m) => {
                  const maxAbs = Math.max(...monthly_pnl.map((x) => Math.abs(x.pnl)), 1);
                  const heightPct = (Math.abs(m.pnl) / maxAbs) * 100;
                  return (
                    <div key={m.month} className="flex-1 flex flex-col items-center gap-1">
                      <span className={`text-xs font-medium ${m.pnl >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                        {m.pnl >= 0 ? '+' : ''}
                        {(m.pnl / 1000).toFixed(1)}k
                      </span>
                      <div className="w-full flex items-end justify-center" style={{ height: '80px' }}>
                        <div
                          className={`w-full rounded-t ${m.pnl >= 0 ? 'bg-emerald-400' : 'bg-red-400'}`}
                          style={{ height: `${heightPct}%`, minHeight: '4px' }}
                        />
                      </div>
                      <span className="text-[10px] text-stone-400">{m.month.slice(5)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {conviction_vs_r && conviction_vs_r.length > 0 && (
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <SectionTitle tooltip="Trades grouped by conviction score at entry — a composite of momentum, structure, relative strength, P/C ratio overlay, and profit-factor overlay. Candidates below 0.55 (longs) or 0.45 (shorts) are hard-blocked and never appear here. Three active tiers: Acceptable (0.55–0.65, 0.85× size), Strong (0.65–0.80, 1.40× size), Exceptional (0.80+, 2.00× size). If higher-tier trades are NOT producing materially better R-multiples, the conviction scoring model needs recalibration.">
                Conviction Score vs R-Multiple
              </SectionTitle>
              <p className="text-xs text-stone-500 mb-4">
                Hard block below 0.55 (longs) / 0.45 (shorts). Three tiers above: 0.85× / 1.40× / 2.00× position size
                multiplier.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {conviction_vs_r.map((b) => (
                  <div key={b.tier} className="bg-stone-50 rounded-lg p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-2">
                      <TipLabel
                        tip={`${b.tier} conviction tier — trades where the composite screener score (momentum + structure + RS) fell in this range at entry. Compare across tiers to validate the screener has a real edge.`}
                        placement="below"
                      >
                        {b.tier}
                      </TipLabel>
                    </p>
                    <p className={`text-xl font-bold ${rColor(b.avg_r)}`}>{fmt(b.avg_r, 2)}R</p>
                    <p className={`text-sm ${wrColor(b.win_rate)}`}>{fmtPct(b.win_rate)} WR</p>
                    <p className="text-xs text-stone-400 mt-1">{b.count} trades</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {top_trades && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {(['best', 'worst'] as const).map((side) => (
                <div key={side} className="bg-white border border-stone-200 rounded-xl p-6">
                  <SectionTitle
                    tooltip={
                      side === 'best'
                        ? 'Top 5 individual closed trades by R-multiple over the analytics lookback window. Useful for reviewing what is driving outsized wins and whether they are repeatable setups.'
                        : 'Bottom 5 individual closed trades by R-multiple. Useful for reviewing what caused the largest losses and whether they share a common pattern to avoid.'
                    }
                  >
                    {side === 'best' ? 'Best 5 Trades' : 'Worst 5 Trades'}
                  </SectionTitle>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-stone-200 text-xs uppercase tracking-wider text-stone-500">
                        <th className="text-left py-2 pr-3">
                          <TipLabel tip="Ticker symbol and strategy tag for this trade">Symbol</TipLabel>
                        </th>
                        <th className="text-right py-2 pr-3">
                          <TipLabel tip="Reward-to-risk multiple: how much was made (or lost) relative to the initial stop-loss risk. R=2.0 means profit was 2× the amount risked.">
                            R
                          </TipLabel>
                        </th>
                        <th className="text-right py-2 pr-3">
                          <TipLabel tip="Realized dollar P&L for this trade">PnL</TipLabel>
                        </th>
                        <th className="text-right py-2">
                          <TipLabel tip="Calendar days held from entry fill to exit fill">Days</TipLabel>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {top_trades[side].map((t, i) => (
                        <tr key={i} className="border-b border-stone-100 last:border-0">
                          <td className="py-1.5 pr-3">
                            <span className="font-semibold text-slate-700">{t.symbol}</span>
                            <span className="ml-1.5 text-[10px] text-stone-400">{t.strategy}</span>
                          </td>
                          <td className={`py-1.5 pr-3 text-right font-medium ${rColor(t.r_multiple)}`}>
                            {fmt(t.r_multiple, 2)}R
                          </td>
                          <td
                            className={`py-1.5 pr-3 text-right text-xs ${
                              t.pnl >= 0 ? 'text-emerald-600' : 'text-red-600'
                            }`}
                          >
                            {fmtPnl(t.pnl)}
                          </td>
                          <td className="py-1.5 text-right text-xs text-stone-400">{t.hold_days ?? '—'}d</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {attribution ? (
        <div className="bg-white border border-stone-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <SectionTitle tooltip={ATTRIBUTION_SECTION_TOOLTIP}>Weekly Strategy Attribution</SectionTitle>
            <span className="text-xs text-stone-400">
              {attribution.generated_at
                ? new Date(attribution.generated_at).toLocaleDateString('en-US', {
                    weekday: 'short',
                    month: 'short',
                    day: 'numeric',
                  })
                : ''}
              {' · '}
              {attribution.lookback_days}d lookback · {attribution.current_regime}
            </span>
          </div>

          {attribution.recommendations?.length > 0 && (
            <div className="mb-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-2">
                <TipLabel tip="Automated recommendations based on rolling profit factor and expectancy. SCALE UP: PF ≥1.5 + positive expectancy. REDUCE: PF 1.0–1.5. PAUSE: PF <1.0 or negative expectancy.">
                  Recommendations
                </TipLabel>
              </p>
              <div className="flex flex-wrap gap-2">
                {attribution.recommendations.map((r, i) => {
                  const action = normalizeAttributionAction(r.action);
                  const strategyLabel = typeof r.strategy === 'string' && r.strategy.length > 0 ? r.strategy : 'Unknown';
                  return (
                  <div
                    key={`${strategyLabel}-${i}`}
                    className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs ${
                      ACTION_COLORS[action] ?? ACTION_COLORS.HOLD
                    }`}
                  >
                    <TipLabel tip={ACTION_TIPS[action] ?? r.reason ?? ''}>
                      <span className="font-bold uppercase tracking-wide">{action.replace(/_/g, ' ')}</span>
                    </TipLabel>
                    <span className="text-stone-500 font-normal">·</span>
                    <span className="font-medium">{strategyLabel}</span>
                    <span className="text-[10px] opacity-70 max-w-[200px] truncate" title={r.reason}>
                      {r.reason ?? ''}
                    </span>
                  </div>
                  );
                })}
              </div>
            </div>
          )}

          {Object.keys(attribution.by_strategy ?? {}).length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-stone-200 text-xs uppercase tracking-wider text-stone-500">
                    <th className="text-left py-2 pr-4">
                      <TipLabel tip="Trading strategy or sub-strategy name">Strategy</TipLabel>
                    </th>
                    <th className="text-right py-2 pr-4">
                      <TipLabel tip="Number of closed trades for this strategy over the lookback period">Trades</TipLabel>
                    </th>
                    <th className="text-right py-2 pr-4">
                      <TipLabel tip="Percentage of closed trades with positive P&L for this strategy">Win Rate</TipLabel>
                    </th>
                    <th className="text-right py-2 pr-4">
                      <TipLabel tip="Gross winning P&L ÷ Gross losing P&L. ≥1.5 is strong (green); ≥2.0 is excellent; 1.0–1.5 is marginal (amber); <1.0 means the strategy is losing more than it makes (red). Primary metric for SCALE UP / PAUSE decisions.">
                        Profit Factor
                      </TipLabel>
                    </th>
                    <th className="text-right py-2 pr-4">
                      <TipLabel tip="Average P&L per trade as a percentage of position size. Formula: (Win Rate × Avg Win%) − (Loss Rate × Avg Loss%). Positive = statistical edge present. Negative = the strategy costs money on average.">
                        Expectancy
                      </TipLabel>
                    </th>
                    <th className="text-right py-2">
                      <TipLabel tip="Average calendar days from entry fill to exit fill for this strategy">Avg Hold</TipLabel>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(attribution.by_strategy).map(([strategy, s]) => (
                    <tr key={strategy} className="border-b border-stone-100 last:border-0">
                      <td className="py-2 pr-4 font-medium text-slate-700">{strategy}</td>
                      <td className="py-2 pr-4 text-right text-stone-600">{s.count}</td>
                      <td className={`py-2 pr-4 text-right ${wrColor(s.win_rate != null ? s.win_rate * 100 : null)}`}>
                        {s.win_rate != null ? fmtPct(s.win_rate * 100) : '—'}
                      </td>
                      <td
                        className={`py-2 pr-4 text-right font-medium ${
                          s.profit_factor == null
                            ? 'text-stone-400'
                            : s.profit_factor >= 1.5
                              ? 'text-emerald-600'
                              : s.profit_factor >= 1.0
                                ? 'text-amber-600'
                                : 'text-red-600'
                        }`}
                      >
                        {s.profit_factor != null ? s.profit_factor.toFixed(2) : '—'}
                      </td>
                      <td
                        className={`py-2 pr-4 text-right ${
                          s.expectancy != null && s.expectancy > 0 ? 'text-emerald-600' : 'text-red-500'
                        }`}
                      >
                        {s.expectancy != null ? `${s.expectancy >= 0 ? '+' : ''}${s.expectancy.toFixed(1)}%` : '—'}
                      </td>
                      <td className="py-2 text-right text-stone-500 text-xs">
                        {s.avg_hold_days != null ? `${s.avg_hold_days.toFixed(1)}d` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="text-xs text-stone-400 mt-4">Generated weekly every Friday.</p>
        </div>
      ) : (
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-5">
          <p className="text-sm font-semibold text-slate-700 mb-1">Strategy Attribution Report</p>
          <p className="text-xs text-stone-500">
            No report found yet. The weekly attribution report generates automatically every Friday. Check back after the
            next run.
          </p>
        </div>
      )}

      <p className="text-xs text-stone-400 text-center pb-2">
        Data sourced from your trade log · Refreshed daily after the U.S. market close · R-multiples and calibration
        targets are back-filled nightly.
      </p>
    </div>
  );
}
