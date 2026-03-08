# Scalable Trading System Architecture: Profitability-Driven Growth (Summary)

Source: Manus AI (2026‑02‑08)

Principles: start lean → scale via profitability triggers → strong observability.

Tiers
- Tier 1: Sonnet coordinator; Gemini Flash scans/research; Kimi sub‑agents; Flash‑Lite heartbeats; 4 concurrency.
- Tier 2: Dedicated trading‑ops pool (Kimi x4–8); parallel scans/backtests; Postgres + Redis; redundancy; 8 concurrency.
- Tier 3: Add local inference (Linux); Opus for complex reasoning; 16 concurrency; TimescaleDB; load balanced webhooks.

Risk: strict caps (risk/trade, max positions, daily/weekly loss, sector exposure). Canary rollout for new strategies.

Upgrade triggers (suggested): T1→T2: $2k/mo × 3; T2→T3: $10k/mo × 3, with quality gates (Sharpe, DD, uptime, trade count).

Roadmap: Phase 0 (foundation) → Phase 1 (shadow) → Phase 2 (paper confirm) → Phase 3 (live T1) → Phase 4 (T2) → Phase 5 (T3).
