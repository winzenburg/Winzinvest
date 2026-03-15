#!/usr/bin/env python3
"""
Combined strategy runner: equity (hybrid NX + AMS) + all four options strategies.

1. Refreshes watchlists via NX multi-mode screener (hybrid universe, sector_strength + premium_selling).
2. Runs the options executor with regime awareness: Covered Calls, CSP, Iron Condors, Protective Puts.

Usage:
  From trading/ or with trading on PYTHONPATH:
    python -m scripts.run_combined_strategy
    python -m scripts.run_combined_strategy --screener-only   # only refresh watchlists
    python -m scripts.run_combined_strategy --options-only   # only run options (no screener)

Optional env: IB_HOST, IB_PORT, etc. (see auto_options_executor and nx_screener_production).
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure scripts and trading are on path
SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(TRADING_DIR) not in sys.path:
    sys.path.insert(0, str(TRADING_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_screener() -> bool:
    """Run NX multi-mode screener to refresh watchlists (sector_strength + premium_selling)."""
    try:
        import subprocess
        screener_script = SCRIPTS_DIR / "nx_screener_production.py"
        result = subprocess.run(
            [sys.executable, str(screener_script), "--mode", "all", "--universe", "full"],
            cwd=str(SCRIPTS_DIR),
            timeout=600,
            capture_output=False,
        )
        if result.returncode != 0:
            logger.warning("Screener exited with code %s", result.returncode)
            return False
        logger.info("Screener finished; watchlists updated")
        return True
    except Exception as e:
        logger.exception("Screener failed: %s", e)
        return False


def run_options_executor() -> bool:
    """Run auto options executor (CC, CSP, Iron Condors, Protective Puts) with regime."""
    try:
        # Import and run main from auto_options_executor
        from auto_options_executor import main as options_main
        options_main()
        return True
    except Exception as e:
        logger.exception("Options executor failed: %s", e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run combined strategy: NX screener + all four options strategies (CC, CSP, IC, PP)",
    )
    parser.add_argument(
        "--screener-only",
        action="store_true",
        help="Only refresh watchlists (NX multi-mode screener); do not run options",
    )
    parser.add_argument(
        "--options-only",
        action="store_true",
        help="Only run options executor (no screener); use existing watchlists",
    )
    args = parser.parse_args()

    logger.info("=== Combined strategy (equity hybrid + options income) ===")

    # Persist current SPY/VIX regime for dashboard (no IB here; uses yfinance)
    if not args.screener_only:
        try:
            from regime_detector import detect_market_regime, persist_regime_to_context
            regime = detect_market_regime(ib=None)
            persist_regime_to_context(regime)
            logger.info("Regime: %s (persisted to regime_context.json)", regime)
        except Exception as e:
            logger.debug("Could not persist regime: %s", e)

    if args.options_only:
        run_options_executor()
        return

    if not args.screener_only:
        if not run_screener():
            logger.warning("Screener had issues; continuing with options anyway")
        run_options_executor()
    else:
        run_screener()


if __name__ == "__main__":
    main()
