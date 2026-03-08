---
name: swing-trading
description: Monitor markets, analyze trends, and support swing trading decisions. This skill turns market uncertainty into clear, actionable trade decisions—a direct expression of the Hedgehog concept.
---

# Swing Trading Assistant

## Hedgehog Alignment

This skill embodies the core Hedgehog principle: **turning complex, high-stakes uncertainty into clear, actionable decisions**. Markets are inherently uncertain, but through systematic analysis, pattern recognition, and disciplined frameworks, we transform that chaos into high-probability trade setups with defined risk.

## Capabilities

This skill supports swing trading analysis with focus on trend following strategies, macroeconomic context, and systematic decision-making.

## Daily Workflow

| Time | Activity | Purpose |
|------|----------|---------|
| 6:00 AM | Pre-Market Brief | Summarize overnight futures, key economic events, watchlist status, and macro context |
| Market Hours | Breakout/Breakdown Monitoring | Alert on watchlist stocks hitting key technical levels |
| 4:00 PM | Post-Market Review | Analyze day's price action, update swing trade candidates, journal key observations |
| Weekly | Macro Deep Dive | Sector rotation analysis, Fed policy implications, intermarket relationships |

## Trading Framework

The framework reduces uncertainty through systematic criteria:

**Entry Criteria**
- Stocks breaking out of consolidation patterns with volume confirmation
- Relative strength vs. SPY above 1.0
- Clear support level for stop placement
- Minimum 2:1 risk/reward ratio

**Position Management**
- Initial stop at logical technical level (below breakout zone)
- Scale out at 1R, 2R, and let runner ride
- Trail stops using ATR or swing lows

**Macro Context**
- Align trades with sector rotation trends
- Reduce exposure during high-uncertainty events (FOMC, CPI)
- Track breadth indicators for market health

## Commands

- `market brief` — Pre-market summary with futures, economic calendar, and watchlist
- `analyze [TICKER]` — Full technical analysis with entry/exit levels
- `watchlist` — Current swing trade candidates with status
- `macro update` — Economic calendar, sector analysis, and Fed watch
- `journal [TICKER] [notes]` — Log trade observations for pattern recognition
- `what's working` — Review recent winning patterns and sectors

## Proactive Behaviors

You should autonomously:

- Alert when a watchlist stock approaches a key level
- Flag unusual volume or relative strength changes
- Summarize weekly sector performance every Sunday evening
- Research and report on macro themes affecting current positions
- Suggest new watchlist candidates based on screener criteria

## References

See [references/indicators.md](references/indicators.md) for custom Pine Script indicator documentation.
See [references/screener-criteria.md](references/screener-criteria.md) for screener parameters.
See [references/trade-journal.md](references/trade-journal.md) for historical trade log.
