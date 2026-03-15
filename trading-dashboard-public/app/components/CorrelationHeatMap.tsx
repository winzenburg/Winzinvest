'use client';

import { useMemo } from 'react';
import { useTradingMode } from '../context/TradingModeContext';
import Tooltip from './Tooltip';

interface CorrelationData {
  symbols: string[];
  matrix: number[][];
}

interface Props {
  data: CorrelationData | null | undefined;
}

function correlationColor(value: number, dark: boolean): string {
  const abs = Math.abs(value);
  if (value >= 0.8) return dark ? 'bg-red-900/80 text-red-200' : 'bg-red-200 text-red-900';
  if (value >= 0.6) return dark ? 'bg-orange-900/60 text-orange-200' : 'bg-orange-100 text-orange-800';
  if (value >= 0.3) return dark ? 'bg-yellow-900/40 text-yellow-200' : 'bg-yellow-50 text-yellow-800';
  if (value >= -0.3) return dark ? 'bg-slate-700 text-stone-300' : 'bg-stone-50 text-stone-600';
  if (value >= -0.6) return dark ? 'bg-blue-900/40 text-blue-200' : 'bg-blue-50 text-blue-800';
  return dark ? 'bg-blue-900/80 text-blue-200' : 'bg-blue-200 text-blue-900';
}

function avgCorrelation(matrix: number[][]): number {
  if (matrix.length < 2) return 0;
  let sum = 0;
  let count = 0;
  for (let i = 0; i < matrix.length; i++) {
    for (let j = i + 1; j < matrix[i].length; j++) {
      sum += matrix[i][j];
      count++;
    }
  }
  return count > 0 ? sum / count : 0;
}

export default function CorrelationHeatMap({ data }: Props) {
  const { viewMode } = useTradingMode();
  const isLive = viewMode === 'live';

  const avg = useMemo(
    () => (data?.matrix ? avgCorrelation(data.matrix) : 0),
    [data?.matrix],
  );

  if (!data || !data.symbols.length || !data.matrix.length) {
    return null;
  }

  const { symbols, matrix } = data;
  const bg = isLive ? 'bg-slate-800 border-slate-700' : 'bg-white border-stone-200';
  const labelColor = isLive ? 'text-stone-400' : 'text-stone-500';
  const headerColor = isLive ? 'text-stone-300' : 'text-stone-600';

  return (
    <div className={`${bg} border rounded-xl p-6 ${isLive ? 'card-elevated-dark' : 'card-elevated'}`}>
      <div className="flex items-center justify-between mb-4">
        <Tooltip text="Pairwise 60-day return correlations for your top 15 holdings. High correlation (red) means concentrated risk." placement="above">
          <h3 className={`text-xs font-semibold uppercase tracking-wider ${labelColor}`}>
            Correlation Matrix
          </h3>
        </Tooltip>
        <div className={`text-xs ${labelColor}`}>
          Avg: <span className={avg > 0.6 ? 'text-red-600 font-semibold' : avg > 0.3 ? 'text-orange-500' : 'text-green-600'}>
            {avg.toFixed(2)}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full table-fixed text-[11px] leading-tight">
          <colgroup>
            {/* row-label column: fixed width; data columns share the rest equally */}
            <col style={{ width: '3rem' }} />
            {symbols.map((sym) => <col key={sym} />)}
          </colgroup>
          <thead>
            <tr>
              <th className="w-12" />
              {symbols.map((sym) => (
                <th
                  key={sym}
                  className={`py-1 font-semibold ${headerColor}`}
                  style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
                >
                  {sym}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map((rowSym, i) => (
              <tr key={rowSym}>
                <td className={`pr-2 font-semibold text-right ${headerColor} whitespace-nowrap`}>
                  {rowSym}
                </td>
                {matrix[i].map((val, j) => {
                  const isDiag = i === j;
                  return (
                    <td
                      key={`${rowSym}-${symbols[j]}`}
                      className={`py-1.5 text-center font-mono ${
                        isDiag
                          ? isLive ? 'bg-stone-700 text-stone-500' : 'bg-stone-200 text-stone-400'
                          : correlationColor(val, isLive)
                      }`}
                      title={`${rowSym} × ${symbols[j]}: ${val.toFixed(3)}`}
                    >
                      {isDiag ? '—' : val.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-4 mt-4">
        <div className="flex items-center gap-1">
          <div className={`w-3 h-3 rounded-sm ${isLive ? 'bg-blue-900/80' : 'bg-blue-200'}`} />
          <span className={`text-[10px] ${labelColor}`}>Negative</span>
        </div>
        <div className="flex items-center gap-1">
          <div className={`w-3 h-3 rounded-sm ${isLive ? 'bg-stone-800' : 'bg-stone-50'}`} />
          <span className={`text-[10px] ${labelColor}`}>Low</span>
        </div>
        <div className="flex items-center gap-1">
          <div className={`w-3 h-3 rounded-sm ${isLive ? 'bg-orange-900/60' : 'bg-orange-100'}`} />
          <span className={`text-[10px] ${labelColor}`}>Moderate</span>
        </div>
        <div className="flex items-center gap-1">
          <div className={`w-3 h-3 rounded-sm ${isLive ? 'bg-red-900/80' : 'bg-red-200'}`} />
          <span className={`text-[10px] ${labelColor}`}>High</span>
        </div>
      </div>
    </div>
  );
}
