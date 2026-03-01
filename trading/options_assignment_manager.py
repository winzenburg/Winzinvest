#!/usr/bin/env python3
"""
Options Assignment Risk Management System
Prevents unwanted assignment on covered calls and cash-secured puts
Tracks assignment probability and enforces rules to keep positions safe
"""

import json
import logging
import math
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import os

try:
    import yfinance as yf
    import numpy as np
    from scipy.stats import norm
except ImportError:
    print("ERROR: Missing dependencies. Install: pip install yfinance numpy scipy")
    exit(1)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
TRADING_DIR = Path(__file__).resolve().parents[0]
LOGS_DIR = TRADING_DIR / 'logs'
TRACKING_FILE = TRADING_DIR / 'logs' / 'options_tracking.json'
RISK_FILE = TRADING_DIR / 'risk.json'
PORTFOLIO_FILE = TRADING_DIR / 'portfolio.json'
EARNINGS_CACHE = TRADING_DIR / 'cache' / 'earnings_cache.json'

LOGS_DIR.mkdir(exist_ok=True)
(TRADING_DIR / 'cache').mkdir(exist_ok=True)


class AssignmentRisk(Enum):
    """Assignment risk levels"""
    LOW = "LOW"          # <20% probability
    MODERATE = "MODERATE"  # 20-40% probability
    HIGH = "HIGH"        # 40-60% probability
    CRITICAL = "CRITICAL"  # >60% probability


class AssignmentCalculator:
    """Calculate assignment probability using Black-Scholes model"""
    
    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate
    
    def get_stock_data(self, symbol: str, period: str = '60d') -> Optional[Dict]:
        """Fetch stock data from yfinance"""
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period=period)
            info = stock.info
            
            if hist.empty:
                return None
            
            current_price = float(hist['Close'].iloc[-1])
            historical_volatility = float(hist['Close'].pct_change().std() * math.sqrt(252))
            
            return {
                'current_price': current_price,
                'historical_vol': historical_volatility,
                'iv': info.get('impliedVolatility', historical_volatility),  # Fallback to HV
                'dividend_yield': info.get('dividendYield', 0.0),
                'trading_volume': info.get('volume', 0),
                'shares_outstanding': info.get('sharesOutstanding', 0)
            }
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def black_scholes_call(self, S: float, K: float, T: float, r: float, sigma: float, 
                          q: float = 0.0) -> Tuple[float, float]:
        """
        Black-Scholes option pricing
        S: Current stock price
        K: Strike price
        T: Time to expiration (years)
        r: Risk-free rate
        sigma: Volatility
        q: Dividend yield
        Returns: (call_price, delta)
        """
        if T <= 0 or sigma <= 0:
            return 0.0, 0.0
        
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        call_price = S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        delta = math.exp(-q * T) * norm.cdf(d1)
        
        return call_price, delta
    
    def itm_probability(self, S: float, K: float, T: float, r: float, sigma: float,
                       q: float = 0.0) -> float:
        """Calculate probability of option finishing ITM"""
        if T <= 0 or sigma <= 0:
            return 1.0 if S > K else 0.0
        
        d2 = (math.log(S / K) + (r - q - 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        return norm.cdf(d2)
    
    def early_assignment_risk(self, symbol: str, strike: float, dte: int, 
                             option_type: str = 'call') -> float:
        """
        Estimate early assignment risk (for American options)
        Factors: delta, dividend yield, time decay, volatility
        """
        stock_data = self.get_stock_data(symbol)
        if not stock_data:
            return 0.0
        
        S = stock_data['current_price']
        sigma = stock_data['iv'] if stock_data['iv'] > 0 else stock_data['historical_vol']
        q = stock_data['dividend_yield']
        T = max(dte / 365.0, 0.001)
        
        # Calculate delta
        _, delta = self.black_scholes_call(S, strike, T, self.risk_free_rate, sigma, q)
        
        if option_type == 'put':
            delta = delta - 1.0  # Put delta = call delta - 1
            delta = abs(delta)
        
        # Risk factors:
        # 1. ITM depth (higher delta = deeper ITM = higher assignment risk)
        # 2. Dividend yield (higher dividends = higher early assignment on calls)
        # 3. Time decay (less time = higher risk)
        # 4. Volatility (lower vol = higher risk relative to value)
        
        if option_type == 'call' and S > strike:
            # ITM call - dividend yield matters
            div_component = min(q * 100, 50)  # 0-50% based on div yield
            delta_component = delta * 100
            time_component = max(0, (40 - dte) * 2) if dte < 40 else 0  # Spike near expiration
            vol_component = max(0, (0.3 - sigma) * 50) if sigma < 0.3 else 0  # Low vol = high risk
            
            risk = (delta_component * 0.5 + div_component * 0.2 + 
                   time_component * 0.2 + vol_component * 0.1)
        else:
            # ITM put - different mechanics
            delta_component = delta * 100
            time_component = max(0, (40 - dte) * 2) if dte < 40 else 0
            vol_component = max(0, (0.3 - sigma) * 50) if sigma < 0.3 else 0
            
            risk = delta_component * 0.6 + time_component * 0.25 + vol_component * 0.15
        
        return min(risk, 100.0)
    
    def calculate_assignment_probability(self, symbol: str, strike: float, dte: int,
                                        option_type: str = 'call') -> Dict:
        """
        Calculate comprehensive assignment probability for an option
        Returns: {
            'symbol': str,
            'strike': float,
            'dte': int,
            'type': str,
            'itm_probability': float (0-100%),
            'early_assignment_risk': float (0-100%),
            'assignment_likelihood': float (0-100%),
            'risk_level': AssignmentRisk,
            'recommendation': str,
            'details': Dict
        }
        """
        stock_data = self.get_stock_data(symbol)
        if not stock_data:
            return {
                'symbol': symbol,
                'strike': strike,
                'dte': dte,
                'type': option_type,
                'error': 'Unable to fetch stock data',
                'assignment_likelihood': 0.0,
                'risk_level': AssignmentRisk.LOW.value
            }
        
        S = stock_data['current_price']
        sigma = stock_data['iv'] if stock_data['iv'] > 0 else stock_data['historical_vol']
        q = stock_data['dividend_yield']
        T = max(dte / 365.0, 0.001)
        
        # Calculate ITM probability
        if option_type == 'call':
            itm_prob = self.itm_probability(S, strike, T, self.risk_free_rate, sigma, q)
        else:  # put
            itm_prob = 1.0 - self.itm_probability(S, strike, T, self.risk_free_rate, sigma, q)
        
        # Calculate early assignment risk
        early_risk = self.early_assignment_risk(symbol, strike, dte, option_type)
        
        # Combined assignment likelihood
        # Only assigned if ITM at expiration (prob) OR early assignment (risk)
        # Combined: P(assignment) = P(ITM) + P(early assignment | ITM)
        assignment_likelihood = itm_prob * 100 + early_risk * itm_prob / 100
        assignment_likelihood = min(assignment_likelihood, 100.0)
        
        # Determine risk level
        if assignment_likelihood < 20:
            risk_level = AssignmentRisk.LOW
        elif assignment_likelihood < 40:
            risk_level = AssignmentRisk.MODERATE
        elif assignment_likelihood < 60:
            risk_level = AssignmentRisk.HIGH
        else:
            risk_level = AssignmentRisk.CRITICAL
        
        # Generate recommendation
        if risk_level == AssignmentRisk.CRITICAL or assignment_likelihood > 70:
            recommendation = f"❌ DO NOT SELL - {assignment_likelihood:.1f}% assignment risk"
        elif risk_level == AssignmentRisk.HIGH:
            recommendation = f"⚠️ HIGH RISK - {assignment_likelihood:.1f}% assignment, only if willing to be assigned"
        elif risk_level == AssignmentRisk.MODERATE:
            recommendation = f"🟡 ACCEPTABLE - {assignment_likelihood:.1f}% assignment risk, monitor closely"
        else:
            recommendation = f"✅ LOW RISK - {assignment_likelihood:.1f}% assignment risk"
        
        return {
            'symbol': symbol,
            'strike': strike,
            'dte': dte,
            'type': option_type,
            'current_price': S,
            'moneyness': (S - strike) / strike if option_type == 'call' else (strike - S) / S,
            'itm_probability': itm_prob * 100,
            'early_assignment_risk': early_risk,
            'assignment_likelihood': assignment_likelihood,
            'risk_level': risk_level.value,
            'recommendation': recommendation,
            'implied_volatility': sigma * 100,
            'dividend_yield': q * 100,
            'trading_volume': stock_data['trading_volume'],
            'timestamp': datetime.now().isoformat()
        }


class EarningsAwarenessChecker:
    """Check earnings dates and enforce earnings-aware rules"""
    
    def __init__(self):
        self.earnings_cache = {}
        self._load_earnings_cache()
    
    def _load_earnings_cache(self):
        """Load earnings dates from cache"""
        if EARNINGS_CACHE.exists():
            try:
                with open(EARNINGS_CACHE, 'r') as f:
                    data = json.load(f)
                    self.earnings_cache = data.get('data', {})
                    logger.info(f"✅ Loaded earnings cache with {len(self.earnings_cache)} symbols")
            except Exception as e:
                logger.warning(f"Could not load earnings cache: {e}")
    
    def get_next_earnings_date(self, symbol: str) -> Optional[datetime]:
        """Get next earnings date for symbol"""
        if symbol in self.earnings_cache:
            try:
                earnings_str = self.earnings_cache[symbol]
                return datetime.fromisoformat(earnings_str) if isinstance(earnings_str, str) else earnings_str
            except Exception:
                pass
        
        # Fallback: try to fetch from yfinance
        try:
            stock = yf.Ticker(symbol)
            earnings_dates = stock.quarterly_financials.columns if hasattr(stock, 'quarterly_financials') else []
            if earnings_dates:
                latest_earnings = earnings_dates[0]
                if isinstance(latest_earnings, str):
                    return datetime.fromisoformat(latest_earnings)
                else:
                    return latest_earnings
        except Exception:
            pass
        
        return None
    
    def days_to_earnings(self, symbol: str) -> Optional[int]:
        """Days until next earnings announcement"""
        earnings_date = self.get_next_earnings_date(symbol)
        if earnings_date:
            days = (earnings_date.date() - datetime.now().date()).days
            return max(days, 0)
        return None
    
    def check_earnings_conflict(self, symbol: str, dte: int, option_type: str = 'call') -> Dict:
        """
        Check if selling an option conflicts with earnings
        Returns: {
            'has_earnings_conflict': bool,
            'earnings_in_days': int or None,
            'recommendation': str,
            'severity': 'CRITICAL' | 'HIGH' | 'NONE'
        }
        """
        days_to_earnings = self.days_to_earnings(symbol)
        
        if days_to_earnings is None:
            return {
                'has_earnings_conflict': False,
                'earnings_in_days': None,
                'recommendation': 'Could not determine earnings date',
                'severity': 'NONE'
            }
        
        # Rule: Don't sell options if earnings within 3 days
        if days_to_earnings <= 3 and days_to_earnings >= 0:
            if option_type == 'call':
                recommendation = f"❌ BLOCKED - Earnings in {days_to_earnings}d. Selling calls on earnings holders forces unwanted assignment."
                severity = 'CRITICAL'
            else:  # put
                recommendation = f"❌ BLOCKED - Earnings in {days_to_earnings}d. Selling puts forces you to be a forced buyer at worst time."
                severity = 'CRITICAL'
            
            return {
                'has_earnings_conflict': True,
                'earnings_in_days': days_to_earnings,
                'recommendation': recommendation,
                'severity': severity,
                'suggestion': 'Sell monthlies (45+ DTE) instead of weeklies'
            }
        elif days_to_earnings <= 10 and days_to_earnings > 3:
            # Warning for near-term options
            return {
                'has_earnings_conflict': False,
                'earnings_in_days': days_to_earnings,
                'recommendation': f"⚠️ WARNING - Earnings in {days_to_earnings}d. Increase assignment probability estimates by 20-30%.",
                'severity': 'HIGH'
            }
        else:
            return {
                'has_earnings_conflict': False,
                'earnings_in_days': days_to_earnings,
                'recommendation': f"✅ OK - Earnings in {days_to_earnings}d, safe to trade",
                'severity': 'NONE'
            }


class VolatilityAwarenessFilter:
    """Volatility-aware rules for strike selection"""
    
    @staticmethod
    def calculate_volatility_skew(symbol: str, dte: int = 35) -> Optional[float]:
        """Calculate IV skew (put IV / call IV)"""
        try:
            stock = yf.Ticker(symbol)
            options = stock.options
            
            if not options or len(options) == 0:
                return None
            
            # Find closest expiration to target DTE
            target_date = datetime.now() + timedelta(days=dte)
            closest_exp = min(options, key=lambda x: abs(
                (datetime.strptime(x, '%Y-%m-%d') - target_date).days
            ))
            
            opt_chain = stock.option_chain(closest_exp)
            calls = opt_chain.calls
            puts = opt_chain.puts
            
            # Get ATM IV skew
            atm_iv_call = calls.iloc[(calls['strike'] - stock.info['currentPrice']).abs().argmin()]['impliedVolatility']
            atm_iv_put = puts.iloc[(puts['strike'] - stock.info['currentPrice']).abs().argmin()]['impliedVolatility']
            
            if atm_iv_call > 0:
                skew = atm_iv_put / atm_iv_call
                return skew
        except Exception as e:
            logger.debug(f"Could not calculate skew for {symbol}: {e}")
        
        return None
    
    @staticmethod
    def get_volatility_recommendation(symbol: str, current_iv: float) -> str:
        """Get strike selection recommendation based on volatility"""
        skew = VolatilityAwarenessFilter.calculate_volatility_skew(symbol)
        
        if skew is None:
            return "Unable to determine skew - use standard strike selection"
        
        if current_iv > 0.30:  # High volatility
            if skew > 1.1:
                return "⚠️ HIGH VOL + SKEW - Avoid selling calls near ATM (assignment risk spikes). Sell 10-15% OTM instead."
            else:
                return "🔴 HIGH VOLATILITY - Assignment risk spikes on ATM calls. Sell 8-12% OTM."
        elif current_iv < 0.15:  # Low volatility
            return "🟢 LOW VOLATILITY - Safer to sell calls closer to ATM (5-8% OTM acceptable)."
        else:
            return "🟡 NORMAL VOLATILITY - Standard 8-10% OTM call selling is appropriate."


class PortfolioImpactChecker:
    """Check if assignment would violate portfolio constraints"""
    
    def __init__(self):
        self.risk_config = self._load_risk_config()
        self.portfolio = self._load_portfolio()
    
    def _load_risk_config(self) -> Dict:
        """Load risk configuration"""
        if RISK_FILE.exists():
            with open(RISK_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def _load_portfolio(self) -> Dict:
        """Load current portfolio"""
        if PORTFOLIO_FILE.exists():
            with open(PORTFOLIO_FILE, 'r') as f:
                return json.load(f)
        return {'positions': [], 'summary': {}}
    
    def get_current_sector_exposure(self, symbol: str) -> Dict:
        """Get current sector exposure for a symbol"""
        try:
            stock = yf.Ticker(symbol)
            sector = stock.info.get('sector', 'Unknown')
            
            total_exposure = 0
            for pos in self.portfolio.get('positions', []):
                if pos['symbol'] == symbol:
                    total_exposure += pos.get('market_value', 0)
            
            return {
                'sector': sector,
                'current_exposure': total_exposure,
                'limit': self.risk_config.get('portfolio_limits', {}).get('max_sector_exposure_dollars', 18000)
            }
        except Exception as e:
            logger.warning(f"Could not determine sector: {e}")
            return {}
    
    def check_assignment_impact(self, symbol: str, quantity: int, option_type: str = 'call') -> Dict:
        """
        Check if assignment would violate portfolio limits
        For calls: assignment increases position size
        For puts: assignment creates new position (must have buying power)
        """
        try:
            stock = yf.Ticker(symbol)
            current_price = float(stock.history(period='1d')['Close'].iloc[-1])
            contract_shares = quantity * 100
            assignment_value = contract_shares * current_price
        except Exception:
            return {
                'can_handle_assignment': False,
                'reason': 'Could not fetch stock price'
            }
        
        limits = self.risk_config.get('portfolio_limits', {})
        max_position_size = limits.get('max_position_size_dollars', 9000)
        max_positions = limits.get('max_concurrent_positions', 5)
        
        if option_type == 'call':
            # Check if assignment increases position beyond max size
            current_exposure = 0
            for pos in self.portfolio.get('positions', []):
                if pos['symbol'] == symbol:
                    current_exposure += pos.get('market_value', 0)
            
            new_exposure = current_exposure + assignment_value
            
            if new_exposure > max_position_size:
                return {
                    'can_handle_assignment': False,
                    'reason': f"Assignment would increase {symbol} position to ${new_exposure:.2f}, exceeding max ${max_position_size:.2f}",
                    'current_exposure': current_exposure,
                    'assignment_value': assignment_value,
                    'new_total': new_exposure
                }
        else:  # put
            # Check if we have enough buying power and if new position fits
            current_positions = len([p for p in self.portfolio.get('positions', []) if p['quantity'] > 0])
            
            if current_positions >= max_positions:
                return {
                    'can_handle_assignment': False,
                    'reason': f"Assignment would create new position #{current_positions + 1}, exceeding max {max_positions}",
                    'current_positions': current_positions
                }
            
            if assignment_value > max_position_size:
                return {
                    'can_handle_assignment': False,
                    'reason': f"Assignment would create ${assignment_value:.2f} position, exceeding max ${max_position_size:.2f}",
                    'assignment_value': assignment_value
                }
        
        return {
            'can_handle_assignment': True,
            'reason': 'Portfolio constraints satisfied',
            'assignment_value': assignment_value,
            'current_positions': len([p for p in self.portfolio.get('positions', []) if p['quantity'] > 0])
        }


class OptionsTracker:
    """Track options and maintain permanent log"""
    
    def __init__(self):
        self.tracking_file = TRACKING_FILE
        self._ensure_file()
    
    def _ensure_file(self):
        """Ensure tracking file exists"""
        if not self.tracking_file.exists():
            initial_data = {
                'version': '1.0',
                'created': datetime.now().isoformat(),
                'options': [],
                'alerts': []
            }
            with open(self.tracking_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    def load_tracking(self) -> Dict:
        """Load tracking data"""
        try:
            with open(self.tracking_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {'version': '1.0', 'options': [], 'alerts': []}
    
    def save_tracking(self, data: Dict):
        """Save tracking data"""
        with open(self.tracking_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def log_option(self, symbol: str, strike: float, expiry: str, 
                  option_type: str, assignment_prob: float, alert_status: str):
        """Log an option analysis"""
        tracking = self.load_tracking()
        
        entry = {
            'symbol': symbol,
            'strike': strike,
            'expiry': expiry,
            'type': option_type,
            'assignment_probability': assignment_prob,
            'alert_status': alert_status,
            'timestamp': datetime.now().isoformat()
        }
        
        tracking['options'].append(entry)
        self.save_tracking(tracking)
    
    def add_alert(self, symbol: str, alert_type: str, message: str, severity: str = 'INFO'):
        """Add alert to tracking"""
        tracking = self.load_tracking()
        
        alert = {
            'symbol': symbol,
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }
        
        tracking['alerts'].append(alert)
        self.save_tracking(tracking)


class OptionsAssignmentManager:
    """Main orchestrator for assignment risk management"""
    
    def __init__(self):
        self.calculator = AssignmentCalculator()
        self.earnings_checker = EarningsAwarenessChecker()
        self.volatility_filter = VolatilityAwarenessFilter()
        self.portfolio_checker = PortfolioImpactChecker()
        self.tracker = OptionsTracker()
    
    def check_option_safety(self, symbol: str, strike: float, dte: int, 
                          option_type: str = 'call', quantity: int = 1) -> Dict:
        """
        Comprehensive safety check for an option trade
        Returns: {
            'safe_to_sell': bool,
            'symbol': str,
            'strike': float,
            'dte': int,
            'type': str,
            'checks': {
                'assignment_risk': { ... },
                'earnings_conflict': { ... },
                'volatility_filter': { ... },
                'portfolio_impact': { ... }
            },
            'overall_recommendation': str,
            'alerts': [...]
        }
        """
        alerts = []
        
        # 1. Assignment probability check
        assignment_result = self.calculator.calculate_assignment_probability(
            symbol, strike, dte, option_type
        )
        
        if 'error' in assignment_result:
            return {
                'safe_to_sell': False,
                'symbol': symbol,
                'strike': strike,
                'overall_recommendation': f"❌ ERROR: {assignment_result['error']}",
                'alerts': [assignment_result['error']]
            }
        
        assignment_safe = assignment_result['assignment_likelihood'] <= 40
        if not assignment_safe:
            alerts.append(f"⚠️ HIGH ASSIGNMENT RISK: {assignment_result['assignment_likelihood']:.1f}%")
        
        # 2. Earnings awareness check
        earnings_result = self.earnings_checker.check_earnings_conflict(symbol, dte, option_type)
        
        earnings_safe = not earnings_result['has_earnings_conflict']
        if not earnings_safe:
            alerts.append(f"⚠️ EARNINGS CONFLICT: {earnings_result['recommendation']}")
        
        # 3. Volatility filter
        vol_recommendation = self.volatility_filter.get_volatility_recommendation(
            symbol, assignment_result.get('implied_volatility', 0) / 100
        )
        
        # 4. Portfolio impact check
        portfolio_result = self.portfolio_checker.check_assignment_impact(
            symbol, quantity, option_type
        )
        
        portfolio_safe = portfolio_result['can_handle_assignment']
        if not portfolio_safe:
            alerts.append(f"⚠️ PORTFOLIO CONSTRAINT: {portfolio_result['reason']}")
        
        # Overall recommendation
        all_safe = assignment_safe and earnings_safe and portfolio_safe
        
        if not all_safe:
            reasons = []
            if not assignment_safe:
                reasons.append("high assignment risk")
            if not earnings_safe:
                reasons.append("earnings conflict")
            if not portfolio_safe:
                reasons.append("portfolio constraint")
            overall = f"❌ DO NOT SELL - Issues: {', '.join(reasons)}"
        else:
            overall = f"✅ SAFE TO SELL - All checks passed"
        
        # Log the analysis
        self.tracker.log_option(
            symbol, strike, datetime.now().isoformat(),
            option_type, assignment_result['assignment_likelihood'],
            'SAFE' if all_safe else 'BLOCKED'
        )
        
        return {
            'safe_to_sell': all_safe,
            'symbol': symbol,
            'strike': strike,
            'dte': dte,
            'type': option_type,
            'checks': {
                'assignment_risk': assignment_result,
                'earnings_conflict': earnings_result,
                'volatility_filter': vol_recommendation,
                'portfolio_impact': portfolio_result
            },
            'overall_recommendation': overall,
            'alerts': alerts,
            'timestamp': datetime.now().isoformat()
        }
    
    def format_for_telegram(self, check_result: Dict) -> Tuple[str, str]:
        """Format check result for Telegram notification"""
        symbol = check_result['symbol']
        strike = check_result['strike']
        opt_type = 'CALL' if check_result['type'] == 'call' else 'PUT'
        dte = check_result['dte']
        
        assignment = check_result['checks']['assignment_risk']
        assignment_prob = assignment.get('assignment_likelihood', 0)
        
        earnings = check_result['checks']['earnings_conflict']
        earnings_days = earnings.get('earnings_in_days', '?')
        
        msg = f"""
*{symbol} ${strike} {opt_type} ({dte} DTE)*

📊 *Assignment Risk*: {assignment_prob:.1f}% 
   → {assignment.get('recommendation', 'N/A')}

📅 *Earnings*: {earnings_days} days away
   → {earnings.get('recommendation', 'N/A')}

🎯 *Overall*: {check_result['overall_recommendation']}
"""
        
        status = "✅ APPROVED" if check_result['safe_to_sell'] else "❌ BLOCKED"
        
        return msg, status


def main():
    """Test the system"""
    print("🚀 Options Assignment Manager - Testing\n")
    
    manager = OptionsAssignmentManager()
    
    # Test symbols
    test_cases = [
        {'symbol': 'AAPL', 'strike': 230, 'dte': 35, 'option_type': 'call'},
        {'symbol': 'TSLA', 'strike': 280, 'dte': 21, 'option_type': 'call'},
        {'symbol': 'MSFT', 'strike': 420, 'dte': 14, 'option_type': 'put'},
    ]
    
    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {test['symbol']} ${test['strike']} {test['option_type'].upper()}")
        print('='*60)
        
        result = manager.check_option_safety(**test)
        
        print(f"\n🎯 Overall: {result['overall_recommendation']}")
        
        if result['alerts']:
            print("\n⚠️ Alerts:")
            for alert in result['alerts']:
                print(f"  • {alert}")
        
        print(f"\n📊 Assignment Risk: {result['checks']['assignment_risk'].get('assignment_likelihood', 0):.1f}%")
        print(f"📅 Earnings: {result['checks']['earnings_conflict'].get('earnings_in_days', '?')} days")
        
        msg, status = manager.format_for_telegram(result)
        print(f"\n{msg}")


if __name__ == '__main__':
    main()
