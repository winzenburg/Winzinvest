/**
 * Mission Control Dashboard
 * Unified view of all projects: Kinlet, Swing Trading, Design System, Cultivate
 * 
 * Core sections:
 * 1. Next Best Action Kanban (top priority)
 * 2. Project Health Indicators
 * 3. Real-time Metrics
 * 4. Activity Feed
 */

import React, { useState, useEffect } from "react";
import { NextBestActionKanban } from "./NextBestActionKanban";
import { ProjectHealthCards } from "./ProjectHealthCards";
import { MetricsDashboard } from "./MetricsDashboard";
import { ActivityFeed } from "./ActivityFeed";
import { getTopNBA, NextBestAction, rankActions } from "@/lib/mission-control/ranking";

interface MissionControlProps {
  refreshInterval?: number; // ms
}

export const MissionControl: React.FC<MissionControlProps> = ({
  refreshInterval = 60000,
}) => {
  const [nbaActions, setNbaActions] = useState<NextBestAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  // Fetch NBA actions on mount and refresh interval
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // In production, fetch from API: /api/mission-control/nba
        const actions = getTopNBA(15);
        setNbaActions(rankActions(actions));
        setLastUpdated(new Date());
      } catch (error) {
        console.error("Failed to fetch NBA actions:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  return (
    <div className="space-y-8 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 min-h-screen p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white tracking-tight">
            Mission Control
          </h1>
          <p className="text-slate-400 mt-1">
            Unified view of all projects. What's next?
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm text-slate-400">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Refreshing every {(refreshInterval / 1000).toFixed(0)}s
          </p>
        </div>
      </div>

      {/* Status Bar */}
      <div className="grid grid-cols-4 gap-4">
        <StatusCard
          project="kinlet"
          status="active"
          label="Kinlet GTM"
          value="Launch in progress"
        />
        <StatusCard
          project="trading"
          status="active"
          label="Trading System"
          value="50-stock watchlist live"
        />
        <StatusCard
          project="design-system"
          status="healthy"
          label="Design System"
          value="No critical issues"
        />
        <StatusCard
          project="cultivate"
          status="healthy"
          label="Cultivate"
          value="Dashboard deploying"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-12 gap-8">
        {/* Left: Next Best Action Kanban (8 cols) */}
        <div className="col-span-8">
          <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
            <h2 className="text-xl font-bold text-white mb-4 flex items-center">
              <span className="w-3 h-3 bg-red-500 rounded-full mr-3"></span>
              Next Best Actions
              <span className="ml-3 text-sm font-normal text-slate-400">
                {nbaActions.length} total
              </span>
            </h2>
            {loading ? (
              <div className="text-slate-400 py-8 text-center">
                Loading actions...
              </div>
            ) : (
              <NextBestActionKanban actions={nbaActions} />
            )}
          </div>
        </div>

        {/* Right: Project Health + Metrics (4 cols) */}
        <div className="col-span-4 space-y-6">
          {/* Project Health Cards */}
          <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
            <h3 className="text-lg font-bold text-white mb-4">
              Project Health
            </h3>
            <ProjectHealthCards />
          </div>

          {/* Key Metrics */}
          <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
            <h3 className="text-lg font-bold text-white mb-4">
              Key Metrics
            </h3>
            <MetricsDashboard />
          </div>

          {/* Alert Panel */}
          <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
            <h3 className="font-semibold text-red-300 text-sm mb-2">
              ⚠️ Blockers Detected
            </h3>
            <ul className="text-sm text-red-200 space-y-1">
              <li>
                • Kinlet admin access (18 signups blocked)
              </li>
              <li>
                • IB Gateway market data subscriptions
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Activity Feed (full width) */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
        <h2 className="text-xl font-bold text-white mb-4">
          Activity Feed
        </h2>
        <ActivityFeed />
      </div>
    </div>
  );
};

interface StatusCardProps {
  project: string;
  status: "healthy" | "warning" | "active" | "critical";
  label: string;
  value: string;
}

const StatusCard: React.FC<StatusCardProps> = ({
  project,
  status,
  label,
  value,
}) => {
  const statusColors = {
    healthy: "bg-green-900/30 border-green-700",
    warning: "bg-yellow-900/30 border-yellow-700",
    active: "bg-blue-900/30 border-blue-700",
    critical: "bg-red-900/30 border-red-700",
  };

  const statusDots = {
    healthy: "bg-green-500",
    warning: "bg-yellow-500",
    active: "bg-blue-500",
    critical: "bg-red-500",
  };

  return (
    <div className={`rounded-lg border p-4 ${statusColors[status]}`}>
      <div className="flex items-center mb-2">
        <div className={`w-2 h-2 rounded-full mr-2 ${statusDots[status]}`}></div>
        <p className="text-sm font-medium text-slate-300">{label}</p>
      </div>
      <p className="text-sm text-slate-400">{value}</p>
    </div>
  );
};
