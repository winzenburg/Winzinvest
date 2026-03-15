/**
 * Utilities for exporting dashboard data as CSV or triggering print-to-PDF.
 */

type CsvRow = Record<string, string | number | null | undefined>;

function escapeCsv(value: string | number | null | undefined): string {
  if (value == null) return '';
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildCsv(rows: CsvRow[]): string {
  if (rows.length === 0) return '';
  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(','),
    ...rows.map(row => headers.map(h => escapeCsv(row[h])).join(',')),
  ];
  return lines.join('\n');
}

function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export interface PositionRow {
  symbol: string;
  side: string;
  quantity: number;
  avg_cost: number | null;
  market_price: number | null;
  notional: number;
  unrealized_pnl: number | null;
  return_pct: number | null;
  sector: string;
}

export function exportPositionsCsv(positions: PositionRow[]) {
  const rows: CsvRow[] = positions.map(p => ({
    Symbol: p.symbol,
    Side: p.side,
    Quantity: p.quantity,
    'Avg Cost': p.avg_cost,
    'Market Price': p.market_price,
    'Notional ($)': p.notional,
    'Unrealized P&L ($)': p.unrealized_pnl,
    'Return (%)': p.return_pct,
    Sector: p.sector,
  }));
  const timestamp = new Date().toISOString().slice(0, 10);
  downloadCsv(`positions_${timestamp}.csv`, buildCsv(rows));
}

export interface TradeRow {
  date: string;
  symbol: string;
  strategy: string;
  side: string;
  quantity: number;
  entry: number;
  exit: number;
  pnl: number;
  return_pct: number;
  hold_hours: number;
}

export function exportTradesCsv(trades: TradeRow[]) {
  const rows: CsvRow[] = trades.map(t => ({
    Date: t.date,
    Symbol: t.symbol,
    Strategy: t.strategy,
    Side: t.side,
    Quantity: t.quantity,
    'Entry ($)': t.entry,
    'Exit ($)': t.exit,
    'P&L ($)': t.pnl,
    'Return (%)': t.return_pct,
    'Hold Time (hrs)': t.hold_hours,
  }));
  const timestamp = new Date().toISOString().slice(0, 10);
  downloadCsv(`trades_${timestamp}.csv`, buildCsv(rows));
}

export interface PerformanceSummary {
  period: string;
  total_pnl: number;
  win_rate: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  total_trades: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  best_trade: number;
  worst_trade: number;
}

export function exportPerformanceCsv(summary: PerformanceSummary) {
  const rows: CsvRow[] = [
    { Metric: 'Period', Value: summary.period },
    { Metric: 'Total P&L ($)', Value: summary.total_pnl },
    { Metric: 'Win Rate (%)', Value: summary.win_rate },
    { Metric: 'Sharpe Ratio', Value: summary.sharpe },
    { Metric: 'Sortino Ratio', Value: summary.sortino },
    { Metric: 'Max Drawdown (%)', Value: summary.max_drawdown },
    { Metric: 'Total Trades', Value: summary.total_trades },
    { Metric: 'Profit Factor', Value: summary.profit_factor },
    { Metric: 'Avg Win ($)', Value: summary.avg_win },
    { Metric: 'Avg Loss ($)', Value: summary.avg_loss },
    { Metric: 'Best Trade ($)', Value: summary.best_trade },
    { Metric: 'Worst Trade ($)', Value: summary.worst_trade },
    { Metric: 'Exported At', Value: new Date().toISOString() },
  ];
  const timestamp = new Date().toISOString().slice(0, 10);
  downloadCsv(`performance_${timestamp}.csv`, buildCsv(rows));
}
