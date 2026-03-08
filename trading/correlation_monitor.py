#!/usr/bin/env python3
"""
Correlation Matrix Monitor
Tracks 30-day rolling correlation between holdings
Identifies highly correlated pairs (>0.7)
Calculates portfolio beta vs SPY
Alerts on hidden concentration risk
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import os
import sys
import warnings

# Suppress pandas warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TRADING_DIR = Path(__file__).resolve().parents[0]
LOGS_DIR = TRADING_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

HIGH_CORRELATION_THRESHOLD = 0.70  # Alert if |correlation| > 0.70
PORTFOLIO_BETA_LIMIT = 1.30  # Alert if portfolio beta > 1.30

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    YFINANCE_AVAILABLE = True
except ImportError:
    logger.error("⚠️  yfinance/pandas/numpy required. Install: pip install yfinance pandas numpy")
    YFINANCE_AVAILABLE = False

def get_open_positions():
    """Extract open positions from portfolio.json"""
    portfolio_file = TRADING_DIR / 'portfolio.json'
    
    if not portfolio_file.exists():
        logger.warning("portfolio.json not found")
        return {}
    
    try:
        with open(portfolio_file) as f:
            data = json.load(f)
        
        positions = {}
        for pos in data.get('positions', []):
            symbol = pos.get('symbol')
            quantity = float(pos.get('quantity', 0))
            value = float(pos.get('market_value', 0))
            
            if symbol not in positions:
                positions[symbol] = {'quantity': 0, 'value': 0}
            
            positions[symbol]['quantity'] += quantity
            positions[symbol]['value'] += value
        
        # Filter out closed/zero positions, return unique tickers
        open_tickers = {k for k, v in positions.items() if v['quantity'] != 0}
        return open_tickers
    
    except Exception as e:
        logger.error(f"Error reading portfolio: {e}")
        return set()

def download_price_data(tickers, period='30d'):
    """Download OHLC data for tickers"""
    if not tickers:
        return None
    
    try:
        data = yf.download(
            list(tickers),
            period=period,
            progress=False,
            ignore_tz=True
        )
        
        if data.empty:
            logger.error(f"No price data for {tickers}")
            return None
        
        # Handle single ticker case (returns Series instead of DataFrame)
        if len(tickers) == 1:
            return pd.DataFrame(data['Close'])
        
        return data['Close']
    
    except Exception as e:
        logger.error(f"Error downloading price data: {e}")
        return None

def calculate_correlation_matrix(tickers):
    """Calculate 30-day rolling correlation between tickers"""
    if len(tickers) < 2:
        return {}, {}  # Need at least 2 tickers for correlation
    
    price_data = download_price_data(tickers, period='30d')
    
    if price_data is None or price_data.empty:
        logger.error("Cannot calculate correlation - no price data")
        return {}, {}
    
    try:
        # Calculate daily returns
        returns = price_data.pct_change().dropna()
        
        if returns.empty or len(returns) < 5:
            logger.warning("Insufficient price history for correlation")
            return {}, {}
        
        # Calculate correlation matrix
        corr_matrix = returns.corr()
        
        return corr_matrix, returns
    
    except Exception as e:
        logger.error(f"Error calculating correlation: {e}")
        return {}, {}

def identify_correlated_pairs(corr_matrix, threshold=HIGH_CORRELATION_THRESHOLD):
    """Identify pairs with |correlation| > threshold"""
    pairs = []
    
    if corr_matrix.empty:
        return pairs
    
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            ticker1 = corr_matrix.columns[i]
            ticker2 = corr_matrix.columns[j]
            corr = corr_matrix.iloc[i, j]
            
            if abs(corr) > threshold:
                pairs.append({
                    'ticker1': ticker1,
                    'ticker2': ticker2,
                    'correlation': float(corr),
                    'abs_correlation': float(abs(corr)),
                    'risk_level': 'HIGH' if abs(corr) > 0.8 else 'MEDIUM'
                })
    
    # Sort by absolute correlation (highest first)
    return sorted(pairs, key=lambda x: x['abs_correlation'], reverse=True)

def calculate_portfolio_beta(tickers, returns_df):
    """
    Calculate portfolio beta vs SPY
    Beta = Covariance(Portfolio, SPY) / Variance(SPY)
    """
    if tickers is None or len(tickers) == 0:
        return None
    
    try:
        # Download SPY data for same period
        spy_data = yf.download('SPY', period='30d', progress=False, ignore_tz=True)['Close']
        spy_returns = spy_data.pct_change().dropna()
        
        if spy_returns.empty or returns_df.empty:
            return None
        
        # Align dates
        common_dates = returns_df.index.intersection(spy_returns.index)
        
        if len(common_dates) < 5:
            return None
        
        portfolio_returns = returns_df.loc[common_dates].mean(axis=1)
        spy_returns_aligned = spy_returns.loc[common_dates]
        
        # Calculate beta
        covariance = np.cov(portfolio_returns, spy_returns_aligned)[0, 1]
        spy_variance = np.var(spy_returns_aligned)
        
        if spy_variance == 0:
            return None
        
        beta = covariance / spy_variance
        return float(beta)
    
    except Exception as e:
        logger.warning(f"Could not calculate portfolio beta: {e}")
        return None

def calculate_effective_bets(corr_matrix):
    """
    Calculate effective number of uncorrelated bets
    Lower value = more concentration risk
    
    Formula: 1 / sum(weight_i^2) where weights are equal (1/N)
    Then adjusted by average correlation
    """
    if corr_matrix.empty or len(corr_matrix) < 2:
        return len(corr_matrix)
    
    try:
        n = len(corr_matrix)
        
        # Average absolute correlation
        corr_values = []
        for i in range(n):
            for j in range(i+1, n):
                corr_values.append(abs(corr_matrix.iloc[i, j]))
        
        avg_corr = np.mean(corr_values) if corr_values else 0
        
        # Effective bets with equal weighting
        equal_weight = 1.0 / n
        herfindahl = (equal_weight ** 2) * n
        
        # Adjust for correlation
        effective_n = (1.0 / herfindahl) * (1.0 - avg_corr)
        
        return max(1.0, float(effective_n))
    
    except Exception as e:
        logger.warning(f"Error calculating effective bets: {e}")
        return float(len(corr_matrix))

def generate_correlation_report():
    """Generate daily correlation report"""
    tickers = get_open_positions()
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'num_positions': len(tickers),
        'positions': sorted(list(tickers)),
        'correlation_matrix': {},
        'correlated_pairs': [],
        'portfolio_beta': None,
        'effective_bets': None,
        'concentration_risk': None,
        'alerts': []
    }
    
    if len(tickers) < 2:
        logger.info(f"Only {len(tickers)} position(s) - no correlation analysis needed")
        return report
    
    # Calculate correlations
    corr_matrix, returns_df = calculate_correlation_matrix(tickers)
    
    if corr_matrix.empty:
        logger.warning("Could not calculate correlation matrix")
        return report
    
    # Store correlation matrix
    corr_dict = {}
    for ticker in tickers:
        if ticker in corr_matrix.columns:
            row = {}
            for other in tickers:
                if other in corr_matrix.columns:
                    row[other] = float(corr_matrix.loc[ticker, other])
            corr_dict[ticker] = row
    
    report['correlation_matrix'] = corr_dict
    
    # Find correlated pairs
    pairs = identify_correlated_pairs(corr_matrix)
    report['correlated_pairs'] = pairs
    
    if pairs:
        for pair in pairs:
            msg = f"⚠️ {pair['ticker1']} <-> {pair['ticker2']}: {pair['correlation']:.2f} ({pair['risk_level']})"
            report['alerts'].append(msg)
            logger.warning(msg)
    
    # Calculate portfolio beta
    if not returns_df.empty:
        beta = calculate_portfolio_beta(tickers, returns_df)
        report['portfolio_beta'] = beta
        
        if beta and beta > PORTFOLIO_BETA_LIMIT:
            msg = f"⚠️ Portfolio beta {beta:.2f} exceeds limit {PORTFOLIO_BETA_LIMIT}"
            report['alerts'].append(msg)
            logger.warning(msg)
    
    # Calculate effective bets
    if not corr_matrix.empty:
        eff_bets = calculate_effective_bets(corr_matrix)
        report['effective_bets'] = eff_bets
        
        # Concentration risk assessment
        if eff_bets < 3:
            risk_level = "VERY HIGH"
        elif eff_bets < 5:
            risk_level = "HIGH"
        elif eff_bets < 8:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        report['concentration_risk'] = {
            'effective_bets': eff_bets,
            'level': risk_level,
            'interpretation': f"{len(tickers)} positions, {eff_bets:.1f} effective uncorrelated bets"
        }
        
        if risk_level in ['HIGH', 'VERY HIGH']:
            msg = f"⚠️ Hidden concentration risk: {len(tickers)} positions but only {eff_bets:.1f} effective bets ({risk_level})"
            report['alerts'].append(msg)
            logger.warning(msg)
    
    return report

def save_correlation_report(report):
    """Save correlation report to logs"""
    log_file = LOGS_DIR / 'correlation_matrix.json'
    
    try:
        # Load existing data
        if log_file.exists():
            with open(log_file) as f:
                history = json.load(f)
        else:
            history = {'reports': []}
        
        # Add new report
        history['reports'].append(report)
        
        # Keep last 30 days
        if len(history['reports']) > 30:
            history['reports'] = history['reports'][-30:]
        
        # Also save current state
        history['current'] = report
        
        with open(log_file, 'w') as f:
            json.dump(history, f, indent=2)
        
        logger.info(f"Correlation report saved: {log_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving correlation report: {e}")
        return False

def get_telegram_alert_message(report):
    """Format correlation alerts for Telegram"""
    alerts = report.get('alerts', [])
    
    if not alerts:
        return None
    
    lines = ["📊 *CORRELATION ALERT*\n"]
    
    for alert in alerts:
        lines.append(alert)
    
    # Add summary
    pairs = report.get('correlated_pairs', [])
    if pairs:
        lines.append(f"\nDetected {len(pairs)} highly correlated pairs (>0.70)")
    
    beta = report.get('portfolio_beta')
    if beta:
        lines.append(f"Portfolio Beta vs SPY: {beta:.2f}")
    
    conc = report.get('concentration_risk', {})
    if conc:
        lines.append(f"Effective Bets: {conc.get('effective_bets', 'N/A'):.1f} ({conc.get('level', 'N/A')})")
    
    return "\n".join(lines)

def main():
    """Run daily correlation monitoring"""
    if not YFINANCE_AVAILABLE:
        logger.error("yfinance not available - skipping correlation analysis")
        return 1
    
    logger.info("=" * 60)
    logger.info("CORRELATION MATRIX MONITOR - Daily Check")
    logger.info("=" * 60)
    
    report = generate_correlation_report()
    saved = save_correlation_report(report)
    
    logger.info(f"\nPositions: {report.get('num_positions', 0)}")
    if report.get('positions'):
        logger.info(f"Tickers: {', '.join(report['positions'][:5])}")
        if len(report['positions']) > 5:
            logger.info(f"         + {len(report['positions']) - 5} more")
    
    pairs = report.get('correlated_pairs', [])
    if pairs:
        logger.info(f"\n⚠️ Found {len(pairs)} highly correlated pairs:")
        for pair in pairs[:5]:
            logger.info(f"   {pair['ticker1']}-{pair['ticker2']}: {pair['correlation']:.2f} ({pair['risk_level']})")
        if len(pairs) > 5:
            logger.info(f"   + {len(pairs) - 5} more pairs")
    
    beta = report.get('portfolio_beta')
    if beta is not None:
        status = "✅" if beta <= PORTFOLIO_BETA_LIMIT else "⚠️"
        logger.info(f"\n{status} Portfolio Beta: {beta:.2f} (limit: {PORTFOLIO_BETA_LIMIT})")
    
    conc = report.get('concentration_risk')
    if conc:
        symbol = "✅" if conc['level'] == 'LOW' else "⚠️"
        logger.info(f"\n{symbol} Concentration Risk: {conc['level']}")
        logger.info(f"   {conc['interpretation']}")
    
    alerts = report.get('alerts', [])
    if not alerts:
        logger.info("\n✅ No correlation alerts")
    
    return 0 if not alerts else 1

if __name__ == '__main__':
    sys.exit(main())
