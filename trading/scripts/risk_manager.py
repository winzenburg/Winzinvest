#!/usr/bin/env python3
"""
Risk Management Module
Enforces position sizing, drawdown limits, margin management, and profit-taking rules.
Integrates into options executor and swing trading executor.
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, List
import logging

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "risk_manager.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# CRAWL Phase Risk Limits
CRAWL_PHASE = {
    "risk_per_trade_pct": 0.5,           # 0.5% of equity per trade
    "max_concurrent_positions": 2,        # Max 2 open positions
    "max_position_pct": 20,               # No single position > 20% of portfolio
    "portfolio_heat_alert": 50,           # Alert if margin usage > 50%
    "portfolio_heat_max": 70,             # Hard stop if margin usage > 70%
    "max_drawdown_pct": 10,               # Pause all trading if drawdown > 10%
    "stop_loss_pct": 5,                   # Hard stop-loss: -5%
    "profit_target_rr": 2.0,              # Take 50% profit at 2:1 reward/risk
    "trailing_stop_pct": 15,              # Trailing stop: 15%
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
        elif self.drawdown_pct > 5:
            return "WARNING"
        else:
            return "OK"
    
    @property
    def margin_status(self) -> str:
        if self.margin_usage_pct > 70:
            return "CRITICAL"
        elif self.margin_usage_pct > 50:
            return "WARNING"
        else:
            return "OK"

class RiskManager:
    """
    Enforces risk limits on all trades.
    Prevents overleveraging, excessive drawdown, and position concentration.
    """
    
    def __init__(self, starting_equity: float = 1936950.48):
        self.starting_equity = starting_equity
        self.portfolio_file = Path.home() / ".openclaw" / "workspace" / "trading" / "portfolio.json"
        self.rules = CRAWL_PHASE
        logger.info(f"Risk Manager initialized (Crawl Phase)")
        logger.info(f"Starting equity: ${starting_equity:,.2f}")
    
    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Fetch current portfolio state from IB."""
        try:
            from ib_insync import IB
            
            ib = IB()
            ib.connect('127.0.0.1', 4002, clientId=107)
            
            # Get account summary
            accounts = ib.accountSummary()
            net_liq = 0
            margin_usage = 0
            num_positions = 0
            
            for account in accounts:
                if account.account == 'DU4661622':
                    if account.tag == 'NetLiquidation':
                        net_liq = float(account.value)
                    elif account.tag == 'MaintMarginReq':
                        init_margin = float(account.value)
                    elif account.tag == 'EquityWithLoanValue':
                        eq_with_loan = float(account.value)
            
            # Calculate metrics
            drawdown = ((self.starting_equity - net_liq) / self.starting_equity) * 100
            margin_usage = (init_margin / net_liq * 100) if net_liq > 0 else 0
            
            # Count positions
            if self.portfolio_file.exists():
                with open(self.portfolio_file) as f:
                    portfolio = json.load(f)
                    num_positions = len([p for p in portfolio.get('positions', []) if p['quantity'] != 0])
            
            ib.disconnect()
            
            metrics = PortfolioMetrics(
                total_equity=net_liq,
                current_pnl=net_liq - self.starting_equity,
                margin_usage_pct=margin_usage,
                current_positions=num_positions,
                drawdown_pct=drawdown
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get portfolio metrics: {e}")
            return None
    
    def check_can_trade(self) -> tuple[bool, str]:
        """
        Check if we're allowed to open new positions.
        Returns: (can_trade: bool, reason: str)
        """
        metrics = self.get_portfolio_metrics()
        
        if not metrics:
            return False, "Cannot fetch portfolio metrics"
        
        # Check drawdown
        if metrics.drawdown_pct > self.rules["max_drawdown_pct"]:
            msg = f"CRITICAL: Drawdown {metrics.drawdown_pct:.1f}% exceeds {self.rules['max_drawdown_pct']}% limit. TRADING PAUSED."
            logger.error(msg)
            return False, msg
        
        # Check margin
        if metrics.margin_usage_pct > self.rules["portfolio_heat_max"]:
            msg = f"CRITICAL: Margin usage {metrics.margin_usage_pct:.1f}% exceeds {self.rules['portfolio_heat_max']}% limit. TRADING PAUSED."
            logger.error(msg)
            return False, msg
        
        if metrics.margin_usage_pct > self.rules["portfolio_heat_alert"]:
            logger.warning(f"WARNING: Margin usage {metrics.margin_usage_pct:.1f}% exceeds {self.rules['portfolio_heat_alert']}% alert threshold.")
        
        # Check max positions
        if metrics.current_positions >= self.rules["max_concurrent_positions"]:
            msg = f"Max concurrent positions ({self.rules['max_concurrent_positions']}) reached. Close a position before opening new ones."
            logger.warning(msg)
            return False, msg
        
        logger.info(f"✅ Can trade. Drawdown: {metrics.drawdown_pct:.1f}%, Margin: {metrics.margin_usage_pct:.1f}%, Positions: {metrics.current_positions}")
        return True, "OK"
    
    def validate_position_size(self, symbol: str, qty: int, entry_price: float, stop_loss_price: float) -> tuple[bool, float, str]:
        """
        Validate position sizing based on risk limits.
        Returns: (is_valid: bool, adjusted_qty: float, reason: str)
        """
        metrics = self.get_portfolio_metrics()
        if not metrics:
            return False, 0, "Cannot fetch portfolio metrics"
        
        # Calculate max risk in dollars
        max_risk_per_trade = metrics.total_equity * (self.rules["risk_per_trade_pct"] / 100)
        
        # Calculate loss per share
        loss_per_share = abs(entry_price - stop_loss_price)
        if loss_per_share == 0:
            return False, 0, "Stop-loss equals entry price"
        
        # Calculate max position size based on risk
        max_qty_by_risk = max_risk_per_trade / loss_per_share
        
        # Calculate max position size based on portfolio concentration
        max_position_value = metrics.total_equity * (self.rules["max_position_pct"] / 100)
        max_qty_by_concentration = max_position_value / entry_price
        
        # Use the smaller of the two limits
        max_qty = min(max_qty_by_risk, max_qty_by_concentration)
        
        # Check if requested size exceeds limit
        if qty > max_qty:
            adjusted_qty = int(max_qty)
            msg = f"{symbol}: Requested {qty} shares exceeds limit {adjusted_qty}. Risk: ${max_risk_per_trade:.0f}, Concentration: {self.rules['max_position_pct']}%"
            logger.warning(msg)
            return True, adjusted_qty, msg
        
        actual_risk = qty * loss_per_share
        logger.info(f"✅ {symbol}: {qty} shares valid. Risk: ${actual_risk:.0f} ({actual_risk/metrics.total_equity*100:.2f}% of equity)")
        return True, float(qty), "OK"
    
    def check_profit_taking(self, symbol: str, entry_price: float, current_price: float, position_qty: int) -> tuple[bool, int, str]:
        """
        Check if position should take partial profits.
        Returns: (should_close: bool, close_qty: int, reason: str)
        """
        if position_qty == 0:
            return False, 0, "No position"
        
        # Calculate gain
        gain_per_share = current_price - entry_price
        gain_pct = (gain_per_share / entry_price) * 100
        
        # Profit target: 2x reward/risk ratio
        # If we risked 1%, look for 2% gains
        if gain_pct >= (self.rules["risk_per_trade_pct"] * self.rules["profit_target_rr"]):
            close_qty = int(position_qty * 0.5)  # Close 50%
            gain_total = gain_per_share * close_qty
            logger.info(f"📊 {symbol}: Profit target hit ({gain_pct:.1f}% gain). Close 50% ({close_qty} shares, ${gain_total:.0f} profit).")
            return True, close_qty, f"Profit target: {gain_pct:.1f}%"
        
        return False, 0, f"Gain: {gain_pct:.1f}% (target: {self.rules['risk_per_trade_pct'] * self.rules['profit_target_rr']:.1f}%)"
    
    def check_stop_loss(self, symbol: str, entry_price: float, current_price: float, position_qty: int) -> tuple[bool, int, str]:
        """
        Check if position has hit hard stop-loss.
        Returns: (should_close: bool, close_qty: int, reason: str)
        """
        if position_qty == 0:
            return False, 0, "No position"
        
        # Calculate loss
        loss_per_share = entry_price - current_price
        loss_pct = (loss_per_share / entry_price) * 100
        
        # Hard stop-loss: 5%
        if loss_pct >= self.rules["stop_loss_pct"]:
            loss_total = loss_per_share * position_qty
            logger.error(f"🛑 {symbol}: STOP-LOSS HIT ({loss_pct:.1f}% loss). Close all {position_qty} shares (${loss_total:.0f} loss).")
            return True, position_qty, f"Stop-loss: {loss_pct:.1f}%"
        
        return False, 0, f"Loss: {loss_pct:.1f}% (stop-loss: {self.rules['stop_loss_pct']}%)"
    
    def generate_report(self) -> str:
        """Generate current risk management report."""
        metrics = self.get_portfolio_metrics()
        
        if not metrics:
            return "Cannot generate report"
        
        report = f"""
=== RISK MANAGEMENT REPORT ===
Timestamp: {datetime.now().isoformat()}

PORTFOLIO METRICS:
- Total Equity: ${metrics.total_equity:,.2f}
- Current P&L: ${metrics.current_pnl:,.2f}
- Drawdown: {metrics.drawdown_pct:.2f}% [{metrics.drawdown_status}]
- Margin Usage: {metrics.margin_usage_pct:.2f}% [{metrics.margin_status}]
- Open Positions: {metrics.current_positions}

RISK LIMITS (CRAWL PHASE):
- Risk per trade: {self.rules['risk_per_trade_pct']}% (${metrics.total_equity * self.rules['risk_per_trade_pct'] / 100:,.0f})
- Max concurrent: {self.rules['max_concurrent_positions']} positions
- Max single position: {self.rules['max_position_pct']}% of portfolio
- Margin alert: {self.rules['portfolio_heat_alert']}%
- Margin max: {self.rules['portfolio_heat_max']}%
- Max drawdown: {self.rules['max_drawdown_pct']}%
- Stop-loss: -{self.rules['stop_loss_pct']}%
- Profit target: {self.rules['profit_target_rr']}:1 RR
- Trailing stop: {self.rules['trailing_stop_pct']}%

STATUS:
- Can trade: {self.check_can_trade()[0]}
- Reason: {self.check_can_trade()[1]}
"""
        return report

def main():
    rm = RiskManager()
    print(rm.generate_report())

if __name__ == "__main__":
    main()
