/**
 * Activity Feed
 * Real-time events from all projects
 */

import React from "react";

interface ActivityEvent {
  timestamp: Date;
  project: "kinlet" | "trading" | "design-system" | "cultivate";
  type: "signup" | "trade" | "pr" | "deploy" | "metric" | "alert";
  title: string;
  description?: string;
}

const SAMPLE_ACTIVITY: ActivityEvent[] = [
  {
    timestamp: new Date(),
    project: "cultivate",
    type: "deploy",
    title: "Mission Control Dashboard",
    description: "Unified dashboard deployed to Vercel",
  },
  {
    timestamp: new Date(Date.now() - 5 * 60 * 1000),
    project: "trading",
    type: "metric",
    title: "NX Screener Refresh",
    description: "50 candidates generated from full market scan",
  },
  {
    timestamp: new Date(Date.now() - 15 * 60 * 1000),
    project: "kinlet",
    type: "signup",
    title: "New Signup",
    description: "User from Reddit caregiver community",
  },
  {
    timestamp: new Date(Date.now() - 30 * 60 * 1000),
    project: "design-system",
    type: "pr",
    title: "PR Opened: Accessibility Updates",
    description: "ARIA labels + keyboard navigation",
  },
  {
    timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000),
    project: "trading",
    type: "metric",
    title: "Options Executor Health",
    description: "Watchdog detected and recovered from gateway reconnect",
  },
];

export const ActivityFeed: React.FC = () => {
  return (
    <div className="space-y-4">
      {SAMPLE_ACTIVITY.map((event, i) => (
        <ActivityEventRow key={i} event={event} />
      ))}
    </div>
  );
};

interface ActivityEventRowProps {
  event: ActivityEvent;
}

const ActivityEventRow: React.FC<ActivityEventRowProps> = ({ event }) => {
  const projectColors = {
    kinlet: "text-blue-600",
    trading: "text-purple-600",
    "design-system": "text-green-600",
    cultivate: "text-orange-600",
  };

  const typeEmoji = {
    signup: "👤",
    trade: "📈",
    pr: "🔀",
    deploy: "🚀",
    metric: "📊",
    alert: "⚠️",
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="flex gap-4 pb-4 border-b border-slate-700 last:border-b-0">
      {/* Timestamp */}
      <div className="flex-shrink-0 text-xs text-slate-500 w-16 pt-1">
        {formatTime(event.timestamp)}
      </div>

      {/* Icon + Content */}
      <div className="flex-1">
        <div className="flex items-start gap-3">
          <span className="text-lg flex-shrink-0">{typeEmoji[event.type]}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-white text-sm">
                {event.title}
              </h4>
              <span
                className={`text-xs font-medium ${projectColors[event.project]}`}
              >
                {event.project}
              </span>
            </div>
            {event.description && (
              <p className="text-sm text-slate-400 mt-1">
                {event.description}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
