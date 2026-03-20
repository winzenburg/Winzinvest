'use client';

import { useEffect, useRef } from 'react';

interface EquityPoint {
  date: string;
  equity: number;
  drawdown: number;
}

interface EquityCurveProps {
  data: EquityPoint[];
}

export default function EquityCurve({ data }: EquityCurveProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || !data || data.length === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 20, right: 60, bottom: 40, left: 60 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    ctx.clearRect(0, 0, width, height);

    const equityValues = data.map(d => d.equity);
    const drawdownValues = data.map(d => d.drawdown);
    const minEquity = Math.min(...equityValues);
    const maxEquity = Math.max(...equityValues);
    const minDrawdown = Math.min(...drawdownValues);

    const equityRange = maxEquity - minEquity || 1;
    const equityScale = chartHeight * 0.7 / equityRange;
    const drawdownScale = minDrawdown !== 0 ? chartHeight * 0.3 / Math.abs(minDrawdown) : 0;
    const xDivisor = data.length > 1 ? data.length - 1 : 1;

    ctx.fillStyle = '#f5f5f4';
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = '#e7e5e4';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = padding.top + (chartHeight * 0.7 * i) / 5;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }

    ctx.fillStyle = '#78716c';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const value = maxEquity - (equityRange * i) / 5;
      const y = padding.top + (chartHeight * 0.7 * i) / 5;
      ctx.fillText(`$${(value / 1000).toFixed(0)}K`, padding.left - 10, y + 4);
    }

    ctx.fillStyle = 'rgba(239, 68, 68, 0.1)';
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + chartHeight * 0.7);
    for (let i = 0; i < data.length; i++) {
      const x = padding.left + (i / xDivisor) * chartWidth;
      const y = padding.top + chartHeight * 0.7 + Math.abs(data[i].drawdown) * drawdownScale;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.lineTo(width - padding.right, padding.top + chartHeight * 0.7);
    ctx.lineTo(padding.left, padding.top + chartHeight * 0.7);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = padding.left + (i / xDivisor) * chartWidth;
      const y = padding.top + chartHeight * 0.7 + Math.abs(data[i].drawdown) * drawdownScale;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    ctx.strokeStyle = '#0ea5e9';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = padding.left + (i / xDivisor) * chartWidth;
      const y = padding.top + chartHeight * 0.7 - (data[i].equity - minEquity) * equityScale;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    ctx.fillStyle = '#78716c';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    const dateStep = Math.max(1, Math.floor(data.length / 8));
    for (let i = 0; i < data.length; i += dateStep) {
      const x = padding.left + (i / xDivisor) * chartWidth;
      const date = new Date(data[i].date);
      const label = `${date.getMonth() + 1}/${date.getDate()}`;
      ctx.fillText(label, x, height - padding.bottom + 20);
    }

    ctx.fillStyle = '#1e293b';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Equity', padding.left, padding.top - 5);
    ctx.fillStyle = '#dc2626';
    ctx.fillText('Drawdown', padding.left + 80, padding.top - 5);

  }, [data]);

  if (!data || data.length === 0) {
    return (
      <div className="bg-white border border-slate-200 card-elevated rounded-xl p-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-4">
          Equity Curve (30 Days)
        </h2>
        <p className="text-sm text-slate-500 py-12 text-center">No equity history data yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 card-elevated rounded-xl p-6">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-4">
        Equity Curve (30 Days)
      </h2>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '300px' }}
        className="w-full"
      />
    </div>
  );
}
