# Launch Live Trading System

**ID:** 002  
**Goal:** Swing Trading - Begin live trading with new rules  
**Priority:** Critical  
**Created:** 2026-02-22  
**Due:** 2026-02-24  
**Status:** Backlog  

## Description

Launch live trading system Monday 7:30 AM MT:

- Liquidate all 75 existing positions for clean slate
- Deploy AMS screener + trade engine (verified working)
- Activate macro regime monitoring
- Launch policy news monitoring (TIER 1)
- Monitor first day for anomalies
- Begin daily portfolio email tracking (4 PM MT)

## Context

All systems verified and tested. Trading rules complete (TRADING_RULES.md). Support systems ready: Kelly Criterion, volatility sizing, rebalancing monitor.

**Status:** ✅ All systems ready
**Blockers:** None
**Risk:** First day execution - monitor closely

## Next Actions

1. Pre-market Sunday night: Final verification
2. Monday 7:30 AM: Market opens, screener starts
3. 4:00 PM: First portfolio email
4. Friday 5 PM: First performance review

## Metrics

- TIER 1 success: System stays online, positions entered cleanly
- Win rate target: >55% after 10 trades
- Daily loss limit: -$1,350 (hard stop)
