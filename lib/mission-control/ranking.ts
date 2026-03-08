/**
 * Next Best Action (NBA) Ranking Engine
 * Ranks all project tasks by leverage (impact × urgency)
 */

export interface NextBestAction {
  id: string;
  title: string;
  project: "kinlet" | "trading" | "design-system" | "cultivate";
  impact: "critical" | "high" | "medium" | "low";
  urgency: "now" | "today" | "this-week" | "backlog";
  status: "blocked" | "ready" | "in-progress" | "done";
  context: string; // Why this matters
  owner?: string;
  linkedItems?: string[]; // GitHub issues, PRs, etc.
  createdAt: Date;
  dueAt?: Date;
}

// Impact score: how much does this move the needle?
const IMPACT_SCORES = {
  critical: 100, // Game-changing (GTM launch, critical bug, major feature)
  high: 75,      // Significant progress (new feature, optimization, major fix)
  medium: 50,    // Incremental value (polish, documentation, minor feature)
  low: 25,       // Nice-to-have (refactor, tech debt, cleanup)
};

// Urgency score: how time-sensitive is this?
const URGENCY_SCORES = {
  now: 100,           // Do immediately (customer impact, blocking others)
  today: 75,          // Same day (deadline approaching, blocking self)
  "this-week": 50,    // This week (flexibility in timing)
  backlog: 25,        // Future (nice-to-have, can defer)
};

// Status decay: completed items drop out, blocked items rise (need unblocking)
const STATUS_MULTIPLIER = {
  blocked: 1.5,      // Increase priority (needs attention to unblock)
  ready: 1.0,        // Normal
  "in-progress": 0.9, // Slightly lower (already happening)
  done: 0,           // Remove from list
};

export function calculateLeverage(action: NextBestAction): number {
  const impactScore = IMPACT_SCORES[action.impact] || 0;
  const urgencyScore = URGENCY_SCORES[action.urgency] || 0;
  const statusMultiplier = STATUS_MULTIPLIER[action.status] || 1.0;
  
  // Leverage = (impact × urgency) × status_multiplier
  // Scale to 0-100
  const leverage = ((impactScore + urgencyScore) / 2) * statusMultiplier;
  
  return Math.round(leverage);
}

export function rankActions(actions: NextBestAction[]): NextBestAction[] {
  // Calculate leverage for each
  const withLeverage = actions.map((action) => ({
    ...action,
    leverage: calculateLeverage(action),
  }));
  
  // Filter out completed items
  const active = withLeverage.filter((a) => a.status !== "done");
  
  // Sort by leverage (highest first)
  return active.sort((a, b) => (b.leverage || 0) - (a.leverage || 0));
}

export function groupByProject(
  actions: NextBestAction[]
): Record<string, NextBestAction[]> {
  return actions.reduce((acc, action) => {
    if (!acc[action.project]) {
      acc[action.project] = [];
    }
    acc[action.project].push(action);
    return acc;
  }, {} as Record<string, NextBestAction[]>);
}

// Kanban status transitions
export function getKanbanStatus(
  action: NextBestAction
): "blocked" | "ready" | "in-progress" | "ready-to-publish" | "done" {
  // Project-specific Kanban rules
  if (action.project === "kinlet") {
    // Kinlet GTM flow: Draft → Ready → In Progress → Ready to Publish → Done
    // Map to generic status
    return action.status as any;
  }
  
  return action.status;
}

// Sample NBA actions for each project
export const SAMPLE_NБAS = {
  kinlet: [
    {
      id: "kinlet-1",
      title: "Post 3 Reddit microguides (Caregiver Burnout)",
      project: "kinlet" as const,
      impact: "critical",
      urgency: "now",
      status: "ready" as const,
      context: "GTM launch: 3 Reddit posts about caregiver burnout to attract early adopters",
      owner: "Ryan",
      linkedItems: ["kinlet-reddit-post-1", "kinlet-reddit-post-2", "kinlet-reddit-post-3"],
    },
    {
      id: "kinlet-2",
      title: "Send 9 personalized DM outreach batch (existing signups)",
      project: "kinlet" as const,
      impact: "high",
      urgency: "today",
      status: "blocked" as const,
      context: "Blocked: Waiting for admin access to Kinlet dashboard for email list + referral links",
      owner: "Ryan",
      dueAt: new Date(Date.now() + 24 * 60 * 60 * 1000),
    },
    {
      id: "kinlet-3",
      title: "Resolve admin access blocker",
      project: "kinlet" as const,
      impact: "critical",
      urgency: "now",
      status: "blocked" as const,
      context: "BLOCKER: Need dashboard access to enable email outreach. Without it, loses ~18 signups.",
      owner: "Ryan",
    },
  ],
  trading: [
    {
      id: "trading-1",
      title: "Validate NX screener candidates on charts",
      project: "trading" as const,
      impact: "high",
      urgency: "this-week",
      status: "ready" as const,
      context: "Review top 10 candidates from NX screener against TradingView price action",
      owner: "Ryan",
    },
  ],
  "design-system": [
    {
      id: "design-1",
      title: "Review & merge pending component PRs",
      project: "design-system" as const,
      impact: "medium",
      urgency: "this-week",
      status: "ready" as const,
      context: "2 PRs awaiting review: accessibility updates + component docs",
      owner: "Ryan",
    },
  ],
  cultivate: [
    {
      id: "cultivate-1",
      title: "Ship mission control dashboard",
      project: "cultivate" as const,
      impact: "critical",
      urgency: "today",
      status: "in-progress" as const,
      context: "Unified dashboard for all projects: metrics, activity, next best actions",
      owner: "Ryan",
      dueAt: new Date(Date.now() + 3 * 60 * 60 * 1000),
    },
  ],
};

// Example usage
export function getTopNBA(limit: number = 10): NextBestAction[] {
  const allActions = Object.values(SAMPLE_NБAS).flat();
  return rankActions(allActions).slice(0, limit);
}
