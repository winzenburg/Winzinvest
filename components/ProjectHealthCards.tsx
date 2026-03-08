/**
 * Project Health Cards
 * Shows status of each project at a glance
 */

import React from "react";

interface ProjectHealthData {
  name: string;
  status: "healthy" | "warning" | "critical";
  metrics: Record<string, number>;
  trend: "up" | "down" | "stable";
}

const PROJECT_HEALTH: ProjectHealthData[] = [
  {
    name: "Kinlet",
    status: "critical", // GTM launch underway, needs attention
    metrics: {
      signups: 9,
      activeUsers: 3,
      waitlist: 42,
    },
    trend: "up",
  },
  {
    name: "Trading",
    status: "healthy", // NX screener live, watchdog running
    metrics: {
      positions: 0,
      watchlistSymbols: 50,
      dailyScans: 1,
    },
    trend: "stable",
  },
  {
    name: "Design System",
    status: "healthy", // No critical issues
    metrics: {
      components: 24,
      prPending: 2,
      coverage: 92,
    },
    trend: "up",
  },
  {
    name: "Cultivate",
    status: "healthy", // Core system operational
    metrics: {
      dashboardDeploying: 1,
      apiHealth: 100,
      uptime: 99.9,
    },
    trend: "stable",
  },
];

export const ProjectHealthCards: React.FC = () => {
  return (
    <div className="space-y-3">
      {PROJECT_HEALTH.map((project) => (
        <ProjectHealthCard key={project.name} project={project} />
      ))}
    </div>
  );
};

interface ProjectHealthCardProps {
  project: ProjectHealthData;
}

const ProjectHealthCard: React.FC<ProjectHealthCardProps> = ({ project }) => {
  const statusColors = {
    healthy: { bg: "bg-green-900/30", border: "border-green-700", dot: "bg-green-500" },
    warning: { bg: "bg-yellow-900/30", border: "border-yellow-700", dot: "bg-yellow-500" },
    critical: { bg: "bg-red-900/30", border: "border-red-700", dot: "bg-red-500" },
  };

  const statusEmoji = {
    healthy: "✓",
    warning: "⚠",
    critical: "🔴",
  };

  const trendEmoji = {
    up: "📈",
    down: "📉",
    stable: "➡️",
  };

  const colors = statusColors[project.status];

  return (
    <div
      className={`rounded-lg border ${colors.border} ${colors.bg} p-3`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center">
          <div className={`w-2 h-2 rounded-full mr-2 ${colors.dot}`}></div>
          <h4 className="font-semibold text-slate-100 text-sm">
            {project.name}
          </h4>
        </div>
        <div className="flex gap-1 text-xs">
          <span>{statusEmoji[project.status]}</span>
          <span>{trendEmoji[project.trend]}</span>
        </div>
      </div>

      {/* Metrics */}
      <div className="space-y-1">
        {Object.entries(project.metrics).map(([key, value]) => (
          <div key={key} className="flex justify-between text-xs text-slate-300">
            <span className="text-slate-400">{key}</span>
            <span className="font-medium text-slate-200">
              {typeof value === "number" && value > 90
                ? `${value}%`
                : value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
