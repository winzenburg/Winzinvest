#!/usr/bin/env python3
"""
Advanced Trading Analytics & Enhancements
1. Win/Loss Streak Tracking
2. Kelly Criterion Position Sizing
3. Portfolio Rebalancing Monitor

Based on industry research (Feb 2026)
"""

import json
import math
from datetime import datetime
from pathlib import Path
from collections import deque

class AdvancedTradingAnalytics:
    def __init__(self):
        self.trading_dir = Path(__file__).resolve().parents[1]
        self.analytics_file = self.trading_dir / 'logs' / 'advanced_analytics.json'
        self.load_analytics()
    
    def load_analytics(self):
        """Load existing analytics data"""
        if self.analytics_file.exists():
            self.data = json.loads(self.analytics_file.read_text())
        else:
            self.data = {
                'trades': [],
                'streaks': {},
                'kelly_metrics': {},
                'portfolio_drift': {}
            }
    
    def save_analytics(self):
        """Save analytics data"""
        self.analytics_file.write_text(json.dumps(self.data, indent=2))
    
    # ============================================
    # 1. WIN/LOSS STREAK TRACKING
    # ============================================
    
    def add_trade_result(self, ticker, entry_price, exit_price, profit_loss, hold_days):
        """Log a trade result"""
        is_win = profit_loss > 0
        
        trade = {
            'date': datetime.now().isoformat(),
            'ticker': ticker,
            'entry': entry_price,
            'exit': exit_price,
            'pnl': profit_loss,
            'is_win': is_win,
            'hold_days': hold_days
        }
        
        self.data['trades'].append(trade)
        self.save_analytics()
        
        return trade
    
    def calculate_streaks(self):
        """Calculate win/loss streaks"""
        if not self.data['trades']:
            return None
        
        trades = self.data['trades']
        current_streak = 1
        streak_type = 'win' if trades[0]['is_win'] else 'loss'
        streaks = []
        
        for i in range(1, len(trades)):
            if (trades[i]['is_win'] and streak_type == 'win') or \
               (not trades[i]['is_win'] and streak_type == 'loss'):
                current_streak += 1
            else:
                streaks.append({
                    'type': streak_type,
                    'length': current_streak,
                    'end_trade': i
                })
                streak_type = 'win' if trades[i]['is_win'] else 'loss'
                current_streak = 1
        
        # Add final streak
        streaks.append({
            'type': streak_type,
            'length': current_streak,
            'end_trade': len(trades)
        })
        
        # Calculate current streak
        current_streak_data = streaks[-1] if streaks else None
        
        return {
            'all_streaks': streaks,
            'current_streak': current_streak_data,
            'longest_win_streak': max([s['length'] for s in streaks if s['type'] == 'win'], default=0),
            'longest_loss_streak': max([s['length'] for s in streaks if s['type'] == 'loss'], default=0)
        }
    
    def streak_confidence_adjustment(self):
        """
        Adjust position sizing based on streak psychology
        
        Hot streak (5+ wins): Can increase to full Kelly
        Cold streak (3+ losses): Reduce to half Kelly
        Normal: Use standard sizing
        """
        streaks = self.calculate_streaks()
        if not streaks or not streaks['current_streak']:
            return 1.0  # Normal multiplier
        
        current = streaks['current_streak']
        
        if current['type'] == 'win' and current['length'] >= 5:
            return 1.2  # 20% increase in position size
        elif current['type'] == 'loss' and current['length'] >= 3:
            return 0.5  # 50% reduction in position size
        else:
            return 1.0  # Normal
    
    def get_streak_report(self):
        """Generate streak report for weekly email"""
        streaks = self.calculate_streaks()
        if not streaks:
            return "No trades yet"
        
        current = streaks['current_streak']
        
        report = f"""
        📊 STREAK ANALYSIS
        ==================
        
        Current Streak: {current['length']} {current['type'].upper()}S
        
        Historical Bests:
        - Longest Win Streak: {streaks['longest_win_streak']} wins
        - Longest Loss Streak: {streaks['longest_loss_streak']} losses
        
        Confidence Adjustment: {self.streak_confidence_adjustment():.1%}
        - Hot streak (5+ wins): Size up 20%
        - Cold streak (3+ losses): Size down 50%
        - Normal (other): Standard sizing
        
        Psychology Note: {"🔥 Hot hand - can increase aggression" if current['type'] == 'win' and current['length'] >= 5 else "❄️ Cold streak - reduce exposure" if current['type'] == 'loss' and current['length'] >= 3 else "📈 Normal - stick to rules"}
        """
        
        return report
    
    # ============================================
    # 2. KELLY CRITERION POSITION SIZING
    # ============================================
    
    def calculate_kelly_criterion(self, win_rate, profit_factor):
        """
        Kelly Criterion: K% = W - [(1-W) / R]
        
        W = win probability (0.60 = 60%)
        R = profit factor (avg_win / avg_loss)
        
        Returns: Kelly %, Half Kelly %, Quarter Kelly %
        """
        if win_rate <= 0 or profit_factor <= 0:
            return None
        
        # Kelly formula
        kelly_percent = win_rate - ((1 - win_rate) / profit_factor)
        
        # Safety limits
        kelly_percent = max(0, min(kelly_percent, 0.25))  # Cap at 25%
        
        return {
            'full_kelly': kelly_percent,
            'half_kelly': kelly_percent / 2,
            'quarter_kelly': kelly_percent / 4,
            'recommendation': 'half_kelly'  # Conservative default
        }
    
    def kelly_from_trades(self):
        """Calculate Kelly Criterion from actual trade history"""
        trades = self.data['trades']
        if len(trades) < 10:
            return None  # Need at least 10 trades for accuracy
        
        wins = sum(1 for t in trades if t['is_win'])
        win_rate = wins / len(trades)
        
        winners = [t['pnl'] for t in trades if t['is_win']]
        losers = [abs(t['pnl']) for t in trades if not t['is_win']]
        
        if not winners or not losers:
            return None
        
        avg_winner = sum(winners) / len(winners)
        avg_loser = sum(losers) / len(losers)
        profit_factor = avg_winner / avg_loser if avg_loser > 0 else 0
        
        kelly_data = self.calculate_kelly_criterion(win_rate, profit_factor)
        kelly_data.update({
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'sample_size': len(trades)
        })
        
        return kelly_data
    
    def get_kelly_report(self):
        """Generate Kelly Criterion report"""
        kelly = self.kelly_from_trades()
        if not kelly:
            return "Need 10+ trades for Kelly Criterion calculation"
        
        report = f"""
        💰 KELLY CRITERION POSITION SIZING
        ==================================
        
        Based on {kelly['sample_size']} trades:
        Win Rate: {kelly['win_rate']:.1%}
        Profit Factor: {kelly['profit_factor']:.2f}
        Avg Winner: ${kelly['avg_winner']:.2f}
        Avg Loser: ${kelly['avg_loser']:.2f}
        
        Kelly Recommendations:
        - FULL KELLY: {kelly['full_kelly']:.2%} (aggressive)
        - HALF KELLY: {kelly['half_kelly']:.2%} ⭐ RECOMMENDED
        - QUARTER KELLY: {kelly['quarter_kelly']:.2%} (conservative)
        
        Current Position Sizing: 2% risk/trade (TIER 3)
        Kelly Optimized: {kelly['half_kelly']:.2%} (more efficient)
        
        Action: If Half Kelly > 2%, can safely increase sizing
        """
        
        return report
    
    # ============================================
    # 3. PORTFOLIO REBALANCING MONITOR
    # ============================================
    
    def check_concentration_drift(self, current_weights):
        """
        Check if portfolio has drifted > 5% from target allocation
        
        Target limits:
        - Sector: 25% max
        - Stock: 8% max
        """
        drift_threshold = 0.05  # 5%
        sector_limit = 0.25
        stock_limit = 0.08
        
        drift_alerts = []
        
        # Check sector weights
        for sector, weight in current_weights.get('sectors', {}).items():
            if weight > sector_limit:
                drift = weight - sector_limit
                drift_alerts.append({
                    'type': 'sector_overweight',
                    'name': sector,
                    'current': weight,
                    'limit': sector_limit,
                    'drift': drift,
                    'action': f'Reduce {sector} by {drift:.1%}' if drift > drift_threshold else 'Monitor'
                })
        
        # Check stock weights
        for stock, weight in current_weights.get('stocks', {}).items():
            if weight > stock_limit:
                drift = weight - stock_limit
                drift_alerts.append({
                    'type': 'stock_overweight',
                    'name': stock,
                    'current': weight,
                    'limit': stock_limit,
                    'drift': drift,
                    'action': f'Reduce {stock} by {drift:.1%}' if drift > drift_threshold else 'Monitor'
                })
        
        return drift_alerts
    
    def volatility_based_sizing_adjustment(self, vix_level):
        """
        Adjust position sizing based on VIX (market volatility)
        
        VIX < 15: Normal sizing (low vol)
        VIX 15-20: 90% sizing
        VIX 20-30: 75% sizing
        VIX > 30: 50% sizing (high vol)
        """
        if vix_level < 15:
            return 1.0, "Low volatility - normal sizing"
        elif vix_level < 20:
            return 0.9, "Slightly elevated volatility - reduce 10%"
        elif vix_level < 30:
            return 0.75, "Moderate volatility - reduce 25%"
        else:
            return 0.5, "High volatility - reduce 50%"
    
    def get_rebalancing_report(self, current_weights, vix_level=None):
        """Generate rebalancing report"""
        drift_alerts = self.check_concentration_drift(current_weights)
        
        report = f"""
        ⚖️  PORTFOLIO REBALANCING MONITOR
        ================================
        
        Concentration Drift Check:
        """
        
        if not drift_alerts:
            report += "\n✅ All positions within target limits"
        else:
            report += f"\n⚠️  {len(drift_alerts)} positions exceed limits:\n"
            for alert in drift_alerts:
                report += f"\n  {alert['name']}: {alert['current']:.1%} (limit: {alert['limit']:.1%})"
                report += f"\n  → {alert['action']}"
        
        if vix_level:
            multiplier, description = self.volatility_based_sizing_adjustment(vix_level)
            report += f"\n\nVolatility-Based Sizing:\n"
            report += f"  VIX: {vix_level:.1f}\n"
            report += f"  Adjustment: {multiplier:.0%} sizing\n"
            report += f"  Reason: {description}\n"
        
        return report
    
    # ============================================
    # COMPREHENSIVE REPORT
    # ============================================
    
    def get_full_advanced_report(self, current_weights=None, vix_level=None):
        """Generate comprehensive advanced analytics report"""
        report = f"""
        🚀 ADVANCED TRADING ANALYTICS
        =============================
        Generated: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p MT')}
        
        """
        
        # Streaks
        report += "1️⃣  WIN/LOSS STREAK ANALYSIS\n"
        report += self.get_streak_report()
        report += "\n\n"
        
        # Kelly
        report += "2️⃣  KELLY CRITERION POSITION SIZING\n"
        report += self.get_kelly_report()
        report += "\n\n"
        
        # Rebalancing
        if current_weights or vix_level:
            report += "3️⃣  PORTFOLIO REBALANCING MONITOR\n"
            report += self.get_rebalancing_report(current_weights or {}, vix_level)
        
        return report

# Example usage
if __name__ == "__main__":
    analytics = AdvancedTradingAnalytics()
    
    # Example: Add some trades
    print("📊 Adding example trades...")
    analytics.add_trade_result('AAPL', 150.00, 152.50, 250, 3)
    analytics.add_trade_result('MSFT', 310.00, 308.00, -200, 2)
    analytics.add_trade_result('NVDA', 450.00, 458.00, 800, 5)
    analytics.add_trade_result('TSLA', 240.00, 238.00, -200, 2)
    analytics.add_trade_result('AMZN', 160.00, 165.00, 500, 4)
    
    # Generate reports
    print("\n" + "="*60)
    print(analytics.get_full_advanced_report(
        current_weights={
            'sectors': {
                'Technology': 0.35,  # 35% (over 25% limit)
                'Finance': 0.15,
                'Energy': 0.15,
                'Healthcare': 0.15,
                'Consumer': 0.15,
                'Other': 0.05
            },
            'stocks': {
                'AAPL': 0.12,  # Over 8% limit
                'MSFT': 0.08,  # At limit
                'NVDA': 0.07,
                'TSLA': 0.06,
                'AMZN': 0.05,
                'Others': 0.56
            }
        },
        vix_level=22.5
    ))
