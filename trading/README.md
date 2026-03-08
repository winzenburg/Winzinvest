# Trading

Configuration and scripts for equity and options execution.

## Position sync

Run **`scripts/sync_current_shorts.py`** before the screener so the position filter has current data. It writes `current_short_symbols.json` from IB (or from the execution log if IB is unavailable). Example: `python scripts/sync_current_shorts.py` then `python scripts/nx_screener_production.py --mode all`.

## Risk configuration

Limits for equity shorts and options are defined in **`risk.json`** and loaded via **`scripts/risk_config.py`**. Any webhook or service that places options orders must use the same limits (from `risk_config` / `risk.json`) so daily and monthly caps are enforced consistently across all execution paths.

## TradingView (indicator & screener)

The **AMS Trade Engine NX v2.1** (chart indicator) and **AMS Pro Screener NX v2** run in TradingView and send webhook alerts. For logic, webhook payloads, and how they align with the Python stack (signal validator, executors, NX metrics), see **`docs/TRADINGVIEW_AMS_NX_REFERENCE.md`**. Use the same webhook secret in TradingView and in `TV_WEBHOOK_SECRET` (e.g. in `.env` or `.cursor/.env.local`) so the Signal Validator accepts only your alerts.

## Portfolio snapshot and daily report (Tier 4)

- **`scripts/portfolio_snapshot.py`** — Connects to IB (clientId=105), writes current positions and summary (short/long notional, net liquidation) to **`portfolio.json`**. Run on demand or at EOD.
- **`scripts/daily_report.py`** — Compares `portfolio.json` to `portfolio_previous.json`, writes **`logs/daily_report_YYYY-MM-DD.md`**, then copies `portfolio.json` → `portfolio_previous.json`. Run after the snapshot (e.g. at EOD).
- **`scripts/eod_flow.py`** — Runs snapshot then daily report in sequence. Schedule at or after market close (e.g. cron).
