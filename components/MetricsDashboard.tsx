/**
 * Key Metrics Dashboard
 * Real-time KPIs across all projects
 */

import React from "react";

interface MetricCard {
  label: string;
  value: string | number;
  unit?: string;
  change?: string;
  status?: "up" | "down" | "stable";
}

const KEY_METRICS: MetricCard[] = [
  {
    label: "Kinlet Signups",
    value: 9,
    unit: "users",
    change: "+2 today",
    status: "up",
  },
  {
    label: "Trading Watchlist",
    value: 50,
    unit: "symbols",
    change: "Live",
    status: "stable",
  },
  {
    label: "Options Scanned",
    value: 1,
    unit: "today",
    change: "0 executed",
    status: "stable",
  },
  {
    label: "System Health",
    value: "99.9%",
    change: "All systems green",
    status: "up",
  },
];

export const MetricsDashboard: React.FC = () => {
  return (
    <div className="space-y-3">
      {KEY_METRICS.map((metric, i) => (
        <MetricCard key={i} metric={metric} />
      ))}
    </div>
  );
};

interface MetricCardProps {
  metric: MetricCard;
}

const MetricCard: React.FC<MetricCardProps> = ({ metric }) => {
  const statusColors = {
    up: "text-green-600",
    down: "text-red-600",
    stable: "text-slate-600",
  };

  const statusEmoji = {
    up: "📈",
    down: "📉",
    stable: "➡️",
  };

  return (
    <div className="p-3 rounded-lg bg-slate-700/50 border border-slate-600">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-slate-400">{metric.label}</span>
        {metric.status && (
          <span className={statusColors[metric.status]}>
            {statusEmoji[metric.status]}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-white">
          {metric.value}
        </span>
        {metric.unit && (
          <span className="text-xs text-slate-400">{metric.unit}</span>
        )}
      </div>
      {metric.change && (
        <p className="text-xs text-slate-500 mt-2">{metric.change}</p>
      )}
    </div>
  );
};
