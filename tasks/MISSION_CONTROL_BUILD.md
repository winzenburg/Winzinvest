# Mission Control Dashboard — Build Log

**Started:** Monday, Feb 23, 2026 @ 9:36 AM MT
**Status:** IN PROGRESS
**Goal:** Unified dashboard for all projects (Kinlet, Swing Trading, Design System, Cultivate)

---

## Architecture

### Data Model

**Next Best Action (NBA)**
```typescript
interface NextBestAction {
  id: string;
  title: string;
  project: "kinlet" | "trading" | "design-system" | "cultivate";
  impact: "critical" | "high" | "medium" | "low";
  urgency: "now" | "today" | "this-week" | "backlog";
  owner: string;
  status: "blocked" | "ready" | "in-progress" | "done";
  leverage: number; // 0-100 (impact * urgency)
  owner: string;
  dueAt?: Date;
  linkedItems?: string[]; // Related tasks/PRs/issues
}
```

**Project Health**
```typescript
interface ProjectHealth {
  name: string;
  status: "healthy" | "warning" | "critical";
  metrics: {
    activeUsers?: number;
    signups?: number;
    churn?: number;
    prs?: number;
    ciHealth?: number;
    portfolioValue?: number;
    positionsOpen?: number;
  };
  lastUpdated: Date;
}
```

**Activity Event**
```typescript
interface ActivityEvent {
  timestamp: Date;
  project: string;
  type: "signup" | "trade" | "pr" | "commit" | "deployment" | "metric";
  title: string;
  description?: string;
  metadata?: Record<string, any>;
}
```

### Data Sources

| Project | Source | Update Freq | Data |
|---------|--------|-------------|------|
| **Kinlet** | API/DB | Real-time | Signups, churn, active users |
| **Swing Trading** | IB API, Files | Real-time | Positions, P&L, trades |
| **Design System** | GitHub API | Hourly | PRs, issues, CI status |
| **Cultivate** | DB | Real-time | Metrics, feature flags |

### Components

1. **NextBestActionKanban** — Drag-and-drop board, ranked by leverage
2. **ProjectHealthSummary** — 4-project status cards
3. **KeyMetricsDashboard** — Real-time KPIs
4. **ActivityFeed** — Chronological events
5. **AlertPanel** — Critical items requiring attention

---

## Build Steps

- [ ] 1. Create data aggregation API
- [ ] 2. Implement NBA ranking engine
- [ ] 3. Build React components
- [ ] 4. Integrate real-time updates
- [ ] 5. Deploy to Vercel
- [ ] 6. Connect to Cultivate app

---

## Files to Create

**Backend:**
- `api/mission-control/aggregation.ts` — Data aggregation from all sources
- `api/mission-control/nba.ts` — Next-best-action ranking + API
- `api/mission-control/health.ts` — Project health aggregation

**Frontend:**
- `components/MissionControl.tsx` — Main dashboard component
- `components/NextBestActionKanban.tsx` — Kanban board
- `components/ProjectHealthCards.tsx` — Project status
- `components/MetricsDashboard.tsx` — KPIs
- `components/ActivityFeed.tsx` — Event stream

**Utils:**
- `lib/mission-control/ranking.ts` — NBA ranking algorithm
- `lib/mission-control/formatters.ts` — Data formatting

---

## Next Steps

Starting with data aggregation API...
