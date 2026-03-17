#!/usr/bin/env python3
"""
Risk Management Module.

Enforces position sizing, drawdown limits, margin management, and profit-taking
rules.  Integrates into options executor and swing trading executor.

All broker interaction is injected via ``metrics_fetcher`` — this module never
imports or connects to ib_insync itself.
"""

import json
import logging
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from paths import TRADING_DIR, LOGS_DIR

LOG_DIR = LOGS_DIR
LOG_FILE = LOG_DIR / "risk_manager.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


CRAWL_PHASE = {
    "risk_per_trade_pct": 0.5,
    "max_concurrent_positions": 2,
    "max_position_pct": 20,
    "portfolio_heat_alert": 50,
    "portfolio_heat_max": 70,
    "max_drawdown_pct": 10,
    "stop_loss_pct": 5,
    "profit_target_rr": 2.0,
    "trailing_stop_pct": 15,
}


@dataclass
class PortfolioMetrics:
    """Current portfolio state."""

    total_equity: float
    current_pnl: float
    margin_usage_pct: float
    current_positions: int
    drawdown_pct: float

    @property
    def drawdown_status(self) -> str:
        if self.drawdown_pct > 10:
            return "CRITICAL"
        if self.drawdown_pct > 5:
            return "WARNING"
        return "OK"

    @property
    def margin_status(self) -> str:
        if self.margin_usage_pct > 70:
            return "CRITICAL"
        if self.margin_usage_pct > 50:
            return "WARNING"
        return "OK"


MetricsFetcher = Callable[[], Optional[PortfolioMetrics]]
"""Signature for the injected broker-metrics callback."""


class RiskManager:
    """Enforces risk limits on all trades.

    ``metrics_fetcher`` is a zero-arg callable that returns a
    ``PortfolioMetrics`` instance (or None if the broker is unreachable).
    Executors wire this up using ``broker_data_helpers.fetch_portfolio_metrics_from_ib``
    or any equivalent data source.
    """

    def __init__(
        self,
        starting_equity: float,
        metrics_fetcher: Optional[MetricsFetcher] = None,
    ) -> None:
        if starting_equity <= 0:
            raise ValueError("starting_equity must be positive")
        self.starting_equity = starting_equity
        self.portfolio_file: Path = TRADING_DIR / "portfolio.json"
        self.rules = CRAWL_PHASE
        self._metrics_fetcher = metrics_fetcher
        logger.info("Risk Manager initialized (Crawl Phase), equity=$%s", f"{starting_equity:,.2f}")

    def get_portfolio_metrics(self) -> Optional[PortfolioMetrics]:
        """Delegate to the injected fetcher; return None when unavailable."""
        if self._metrics_fetcher is None:
            logger.warning("No metrics_fetcher configured — cannot fetch portfolio state")
            return None
        try:
            return self._metrics_fetcher()
        except Exception as exc:
            logger.error("metrics_fetcher raised: %s", exc)
            return None

    def check_can_trade(self) -> tuple[bool, str]:
        """Check if we're allowed to open new positions."""
        metrics = self.get_portfolio_metrics()
        if not metrics:
            return False, "Cannot fetch portfolio metrics"

        if metrics.drawdown_pct > self.rules["max_drawdown_pct"]:
            msg = (
                f"CRITICAL: Drawdown {metrics.drawdown_pct:.1f}% exceeds "
                f"{self.rules['max_drawdown_pct']}% limit. TRADING PAUSED."
            )
            logger.error(msg)
            return False, msg

        if metrics.margin_usage_pct > self.rules["portfolio_heat_max"]:
            msg = (
                f"CRITICAL: Margin usage {metrics.margin_usage_pct:.1f}% exceeds "
                f"{self.rules['portfolio_heat_max']}% limit. TRADING PAUSED."
            )
            logger.error(msg)
            return False, msg

        if metrics.margin_usage_pct > self.rules["portfolio_heat_alert"]:
            logger.warning(
                "Margin usage %.1f%% exceeds %s%% alert threshold.",
                metrics.margin_usage_pct,
                self.rules["portfolio_heat_alert"],
            )

        if metrics.current_positions >= self.rules["max_concurrent_positions"]:
            msg = (
                f"Max concurrent positions ({self.rules['max_concurrent_positions']}) reached. "
                "Close a position before opening new ones."
            )
            logger.warning(msg)
            return False, msg

        logger.info(
            "Can trade. Drawdown: %.1f%%, Margin: %.1f%%, Positions: %d",
            metrics.drawdown_pct,
            metrics.margin_usage_pct,
            metrics.current_positions,
        )
        return True, "OK"

    def validate_position_size(
        self,
        symbol: str,
        qty: int,
        entry_price: float,
        stop_loss_price: float,
    ) -> tuple[bool, float, str]:
        """Validate position sizing based on risk limits."""
        metrics = self.get_portfolio_metrics()
        if not metrics:
            return False, 0, "Cannot fetch portfolio metrics"

        max_risk_per_trade = metrics.total_equity * (self.rules["risk_per_trade_pct"] / 100)
        loss_per_share = abs(entry_price - stop_loss_price)
        if loss_per_share == 0:
            return False, 0, "Stop-loss equals entry price"

        max_qty_by_risk = max_risk_per_trade / loss_per_share
        max_position_value = metrics.total_equity * (self.rules["max_position_pct"] / 100)
        max_qty_by_concentration = max_position_value / entry_price
        max_qty = min(max_qty_by_risk, max_qty_by_concentration)

        if qty > max_qty:
            adjusted_qty = int(max_qty)
            msg = (
                f"{symbol}: Requested {qty} shares exceeds limit {adjusted_qty}. "
                f"Risk: ${max_risk_per_trade:.0f}, Concentration: {self.rules['max_position_pct']}%"
            )
            logger.warning(msg)
            return True, adjusted_qty, msg

        actual_risk = qty * loss_per_share
        logger.info(
            "%s: %d shares valid. Risk: $%.0f (%.2f%% of equity)",
            symbol,
            qty,
            actual_risk,
            actual_risk / metrics.total_equity * 100,
        )
        return True, float(qty), "OK"

    def check_profit_taking(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        position_qty: int,
    ) -> tuple[bool, int, str]:
        """Check if position should take partial profits."""
        if position_qty == 0:
            return False, 0, "No position"

        gain_per_share = current_price - entry_price
        gain_pct = (gain_per_share / entry_price) * 100

        target_pct = self.rules["risk_per_trade_pct"] * self.rules["profit_target_rr"]
        if gain_pct >= target_pct:
            close_qty = int(position_qty * 0.5)
            gain_total = gain_per_share * close_qty
            logger.info(
                "%s: Profit target hit (%.1f%% gain). Close 50%% (%d shares, $%.0f profit).",
                symbol,
                gain_pct,
                close_qty,
                gain_total,
            )
            return True, close_qty, f"Profit target: {gain_pct:.1f}%"

        return False, 0, f"Gain: {gain_pct:.1f}% (target: {target_pct:.1f}%)"

    def check_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        position_qty: int,
    ) -> tuple[bool, int, str]:
        """Check if position has hit hard stop-loss."""
        if position_qty == 0:
            return False, 0, "No position"

        loss_per_share = entry_price - current_price
        loss_pct = (loss_per_share / entry_price) * 100

        if loss_pct >= self.rules["stop_loss_pct"]:
            loss_total = loss_per_share * position_qty
            logger.error(
                "%s: STOP-LOSS HIT (%.1f%% loss). Close all %d shares ($%.0f loss).",
                symbol,
                loss_pct,
                position_qty,
                loss_total,
            )
            return True, position_qty, f"Stop-loss: {loss_pct:.1f}%"

        return False, 0, f"Loss: {loss_pct:.1f}% (stop-loss: {self.rules['stop_loss_pct']}%)"

    def generate_report(self) -> str:
        """Generate current risk management report."""
        metrics = self.get_portfolio_metrics()
        if not metrics:
            return "Cannot generate report — metrics unavailable"

        can_trade, reason = self.check_can_trade()
        return (
            f"\n=== RISK MANAGEMENT REPORT ===\n"
            f"Timestamp: {datetime.now().isoformat()}\n\n"
            f"PORTFOLIO METRICS:\n"
            f"- Total Equity: ${metrics.total_equity:,.2f}\n"
            f"- Current P&L: ${metrics.current_pnl:,.2f}\n"
            f"- Drawdown: {metrics.drawdown_pct:.2f}% [{metrics.drawdown_status}]\n"
            f"- Margin Usage: {metrics.margin_usage_pct:.2f}% [{metrics.margin_status}]\n"
            f"- Open Positions: {metrics.current_positions}\n\n"
            f"RISK LIMITS (CRAWL PHASE):\n"
            f"- Risk per trade: {self.rules['risk_per_trade_pct']}%"
            f" (${metrics.total_equity * self.rules['risk_per_trade_pct'] / 100:,.0f})\n"
            f"- Max concurrent: {self.rules['max_concurrent_positions']} positions\n"
            f"- Max single position: {self.rules['max_position_pct']}% of portfolio\n"
            f"- Margin alert: {self.rules['portfolio_heat_alert']}%\n"
            f"- Margin max: {self.rules['portfolio_heat_max']}%\n"
            f"- Max drawdown: {self.rules['max_drawdown_pct']}%\n"
            f"- Stop-loss: -{self.rules['stop_loss_pct']}%\n"
            f"- Profit target: {self.rules['profit_target_rr']}:1 RR\n"
            f"- Trailing stop: {self.rules['trailing_stop_pct']}%\n\n"
            f"STATUS:\n"
            f"- Can trade: {can_trade}\n"
            f"- Reason: {reason}\n"
        )


def main() -> None:
    logger.info("Risk manager report (no broker connected — metrics_fetcher not set)")
    rm = RiskManager(starting_equity=1_000_000)
    logger.info(rm.generate_report())


if __name__ == "__main__":
    main()
