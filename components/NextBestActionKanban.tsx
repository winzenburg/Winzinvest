/**
 * Next Best Action Kanban Board
 * Drag-and-drop board showing actions ranked by leverage
 * 
 * Columns:
 * 1. Blocked (needs unblocking) — ALERT STATE
 * 2. Ready (can start now)
 * 3. In Progress
 * 4. Ready to Publish (content pipeline)
 * 5. Done
 */

import React from "react";
import { NextBestAction } from "@/lib/mission-control/ranking";

interface NextBestActionKanbanProps {
  actions: NextBestAction[];
  onStatusChange?: (actionId: string, newStatus: string) => void;
}

type KanbanColumn = "blocked" | "ready" | "in-progress" | "ready-to-publish" | "done";

const KANBAN_COLUMNS: { key: KanbanColumn; label: string; color: string }[] = [
  { key: "blocked", label: "🚫 Blocked", color: "border-red-500 bg-red-50" },
  { key: "ready", label: "✓ Ready", color: "border-blue-500 bg-blue-50" },
  { key: "in-progress", label: "→ In Progress", color: "border-purple-500 bg-purple-50" },
  { key: "ready-to-publish", label: "📦 Ready to Publish", color: "border-green-500 bg-green-50" },
  { key: "done", label: "✅ Done", color: "border-slate-500 bg-slate-50" },
];

export const NextBestActionKanban: React.FC<NextBestActionKanbanProps> = ({
  actions,
  onStatusChange,
}) => {
  // Group actions by status
  const groupedByStatus = KANBAN_COLUMNS.reduce((acc, col) => {
    acc[col.key] = actions.filter((a) => a.status === col.key);
    return acc;
  }, {} as Record<KanbanColumn, NextBestAction[]>);

  return (
    <div className="flex overflow-x-auto gap-6 pb-4">
      {KANBAN_COLUMNS.map((column) => (
        <KanbanColumn
          key={column.key}
          column={column}
          actions={groupedByStatus[column.key]}
          onStatusChange={onStatusChange}
        />
      ))}
    </div>
  );
};

interface KanbanColumnProps {
  column: { key: KanbanColumn; label: string; color: string };
  actions: NextBestAction[];
  onStatusChange?: (actionId: string, newStatus: string) => void;
}

const KanbanColumn: React.FC<KanbanColumnProps> = ({
  column,
  actions,
  onStatusChange,
}) => {
  return (
    <div className="flex-shrink-0 w-80">
      <div className="mb-4">
        <h3 className="font-semibold text-slate-800">
          {column.label}
          <span className="ml-2 text-sm text-slate-500">
            ({actions.length})
          </span>
        </h3>
      </div>

      <div className={`space-y-3 rounded-lg border-2 p-4 min-h-96 ${column.color}`}>
        {actions.length === 0 ? (
          <p className="text-slate-400 text-sm italic py-8 text-center">
            No items
          </p>
        ) : (
          actions.map((action) => (
            <KanbanCard
              key={action.id}
              action={action}
              column={column.key}
              onStatusChange={onStatusChange}
            />
          ))
        )}
      </div>
    </div>
  );
};

interface KanbanCardProps {
  action: NextBestAction;
  column: KanbanColumn;
  onStatusChange?: (actionId: string, newStatus: string) => void;
}

const KanbanCard: React.FC<KanbanCardProps> = ({
  action,
  column,
  onStatusChange,
}) => {
  const impactColors = {
    critical: "bg-red-200 text-red-900",
    high: "bg-orange-200 text-orange-900",
    medium: "bg-blue-200 text-blue-900",
    low: "bg-slate-200 text-slate-900",
  };

  const urgencyEmoji = {
    now: "🔥",
    today: "⚡",
    "this-week": "📅",
    backlog: "📋",
  };

  // Calculate leverage for display
  const leverage = calculateLeverageForDisplay(action);

  return (
    <div
      className="bg-white rounded-lg p-4 shadow-sm border border-slate-200 hover:shadow-md transition-shadow cursor-move"
      draggable
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <h4 className="font-semibold text-slate-900 text-sm flex-1">
          {action.title}
        </h4>
        <span className="text-lg ml-2">{urgencyEmoji[action.urgency]}</span>
      </div>

      {/* Meta */}
      <div className="space-y-2 mb-3">
        {/* Project */}
        <div className="inline-block">
          <span className="text-xs font-medium px-2 py-1 rounded bg-slate-100 text-slate-700">
            {action.project}
          </span>
        </div>

        {/* Impact */}
        <div>
          <span className={`text-xs font-medium px-2 py-1 rounded ${impactColors[action.impact]}`}>
            {action.impact.toUpperCase()}
          </span>
        </div>

        {/* Leverage Score */}
        <div className="pt-2 border-t border-slate-200">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Leverage</span>
            <span className="font-bold text-slate-900">{leverage}/100</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2 mt-1">
            <div
              className={`h-2 rounded-full ${
                leverage > 75
                  ? "bg-red-500"
                  : leverage > 50
                  ? "bg-orange-500"
                  : leverage > 25
                  ? "bg-blue-500"
                  : "bg-slate-400"
              }`}
              style={{ width: `${leverage}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* Context/Description */}
      {action.context && (
        <p className="text-xs text-slate-600 mb-3 line-clamp-2">
          {action.context}
        </p>
      )}

      {/* Owner + Due Date */}
      <div className="flex items-center justify-between text-xs text-slate-500 mb-3">
        {action.owner && <span>{action.owner}</span>}
        {action.dueAt && (
          <span>
            Due: {action.dueAt.toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        {column !== "done" && (
          <button
            onClick={() => onStatusChange?.(action.id, "done")}
            className="flex-1 text-xs font-medium py-1 px-2 rounded bg-green-100 text-green-700 hover:bg-green-200 transition"
          >
            Complete
          </button>
        )}
        {column === "blocked" && (
          <button
            onClick={() => onStatusChange?.(action.id, "ready")}
            className="flex-1 text-xs font-medium py-1 px-2 rounded bg-blue-100 text-blue-700 hover:bg-blue-200 transition"
          >
            Unblock
          </button>
        )}
      </div>

      {/* Linked Items */}
      {action.linkedItems && action.linkedItems.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-200">
          <p className="text-xs text-slate-500 mb-1">Linked:</p>
          <div className="flex flex-wrap gap-1">
            {action.linkedItems.slice(0, 2).map((item) => (
              <a
                key={item}
                href={`#${item}`}
                className="text-xs text-blue-600 hover:underline"
              >
                {item}
              </a>
            ))}
            {action.linkedItems.length > 2 && (
              <span className="text-xs text-slate-400">
                +{action.linkedItems.length - 2} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

function calculateLeverageForDisplay(action: NextBestAction): number {
  const IMPACT_SCORES = { critical: 100, high: 75, medium: 50, low: 25 };
  const URGENCY_SCORES = { now: 100, today: 75, "this-week": 50, backlog: 25 };
  const STATUS_MULTIPLIER = { blocked: 1.5, ready: 1.0, "in-progress": 0.9, done: 0 };

  const impactScore = IMPACT_SCORES[action.impact] || 0;
  const urgencyScore = URGENCY_SCORES[action.urgency] || 0;
  const statusMultiplier = STATUS_MULTIPLIER[action.status] || 1.0;

  const leverage = ((impactScore + urgencyScore) / 2) * statusMultiplier;
  return Math.round(Math.min(leverage, 100));
}
