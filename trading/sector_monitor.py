#!/usr/bin/env python3
"""
Sector Concentration Monitor
Tracks portfolio sector allocation and enforces concentration limits
- Max 20% per sector (hard limit)
- Monitors daily and alerts on violations
- Prevents entry if sector limit would be exceeded
"""

import json
import logging
from datetime import datetime
from pathlib import Path
import os
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TRADING_DIR = Path(__file__).resolve().parents[0]
LOGS_DIR = TRADING_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Sector mapping: ticker -> sector
SECTOR_MAP = {
    # Energy
    'XLE': 'Energy', 'CVX': 'Energy', 'XOM': 'Energy', 'MPC': 'Energy',
    'PSX': 'Energy', 'EOG': 'Energy', 'SLB': 'Energy', 'MRO': 'Energy',
    'COP': 'Energy', 'DVN': 'Energy', 'OKE': 'Energy', 'HAL': 'Energy',
    'EQT': 'Energy', 'KMI': 'Energy', 'OXY': 'Energy', 'PXD': 'Energy',
    
    # Technology
    'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'GOOG': 'Technology',
    'META': 'Technology', 'NVDA': 'Technology', 'TSLA': 'Technology', 'AMZN': 'Technology',
    'QQQ': 'Technology', 'XLK': 'Technology', 'NFLX': 'Technology', 'CRM': 'Technology',
    'ADBE': 'Technology', 'INTC': 'Technology', 'AMD': 'Technology', 'CSCO': 'Technology',
    'ORCL': 'Technology', 'ACN': 'Technology', 'IBM': 'Technology', 'AVGO': 'Technology',
    
    # Financials
    'XLF': 'Financials', 'JPM': 'Financials', 'BAC': 'Financials', 'WFC': 'Financials',
    'GS': 'Financials', 'MS': 'Financials', 'BLK': 'Financials', 'SPYG': 'Financials',
    'C': 'Financials', 'COF': 'Financials', 'AXP': 'Financials', 'USB': 'Financials',
    'PNC': 'Financials', 'BK': 'Financials', 'SCHW': 'Financials', 'COIN': 'Financials',
    
    # Healthcare
    'XLV': 'Healthcare', 'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'PFE': 'Healthcare',
    'ABBV': 'Healthcare', 'TMO': 'Healthcare', 'MRK': 'Healthcare', 'LLY': 'Healthcare',
    'CI': 'Healthcare', 'AMGN': 'Healthcare', 'ELV': 'Healthcare', 'AZN': 'Healthcare',
    'MDT': 'Healthcare', 'ISRG': 'Healthcare',
    
    # Industrials
    'XLI': 'Industrials', 'BA': 'Industrials', 'CAT': 'Industrials', 'GE': 'Industrials',
    'MMM': 'Industrials', 'HON': 'Industrials', 'LMT': 'Industrials', 'RTX': 'Industrials',
    'UTX': 'Industrials', 'DE': 'Industrials', 'NOC': 'Industrials', 'DAL': 'Industrials',
    'FDX': 'Industrials', 'UPS': 'Industrials', 'GWW': 'Industrials',
    
    # Consumer Discretionary
    'XLY': 'Consumer', 'AMZN': 'Consumer', 'TSLA': 'Consumer', 'MCD': 'Consumer',
    'TM': 'Consumer', 'NKE': 'Consumer', 'LULULEMON': 'Consumer', 'BKNG': 'Consumer',
    'RCL': 'Consumer', 'CCL': 'Consumer', 'ABNB': 'Consumer', 'MKL': 'Consumer',
    
    # Consumer Staples
    'XLP': 'Consumer Staples', 'KO': 'Consumer Staples', 'PEP': 'Consumer Staples',
    'WMT': 'Consumer Staples', 'PG': 'Consumer Staples', 'MO': 'Consumer Staples',
    'PM': 'Consumer Staples', 'DPS': 'Consumer Staples', 'TSN': 'Consumer Staples',
    'TMDX': 'Consumer Staples', 'DG': 'Consumer Staples', 'KMX': 'Consumer Staples',
    
    # Utilities
    'XLU': 'Utilities', 'NEE': 'Utilities', 'SO': 'Utilities', 'DUK': 'Utilities',
    'AEP': 'Utilities', 'EXC': 'Utilities', 'PCG': 'Utilities', 'AWK': 'Utilities',
    
    # Real Estate
    'VNQ': 'Real Estate', 'O': 'Real Estate', 'VICI': 'Real Estate', 'EQIX': 'Real Estate',
    'PLD': 'Real Estate', 'PSA': 'Real Estate', 'WELL': 'Real Estate', 'SPG': 'Real Estate',
    
    # Commodities/Materials
    'XLB': 'Materials', 'REM': 'Materials', 'GLD': 'Materials', 'SLV': 'Materials',
    'FCX': 'Materials', 'NUE': 'Materials', 'CLF': 'Materials', 'AA': 'Materials',
    'CF': 'Materials', 'DOW': 'Materials', 'LYB': 'Materials', 'PPG': 'Materials',
}

MAX_SECTOR_ALLOCATION = 0.20  # 20% max per sector
ALERT_THRESHOLD = 0.18  # 18% - yellow flag for early warning

def get_sector(ticker):
    """Get sector for a ticker. Default to 'Other' if unknown."""
    return SECTOR_MAP.get(ticker.upper(), 'Other')

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
            positions[symbol]['value'] += abs(value)  # Use absolute value
        
        # Filter out closed/zero positions
        return {k: v for k, v in positions.items() if v['quantity'] != 0}
    
    except Exception as e:
        logger.error(f"Error reading portfolio: {e}")
        return {}

def calculate_sector_allocation(positions):
    """
    Calculate sector allocation by market value.
    Returns: {sector: {'value': float, 'pct': float, 'tickers': [list]}}
    """
    total_value = sum(abs(p['value']) for p in positions.values())
    
    if total_value == 0:
        return {}
    
    sector_data = {}
    
    for ticker, pos_data in positions.items():
        sector = get_sector(ticker)
        value = abs(pos_data['value'])
        
        if sector not in sector_data:
            sector_data[sector] = {
                'value': 0,
                'tickers': [],
                'count': 0
            }
        
        sector_data[sector]['value'] += value
        sector_data[sector]['tickers'].append(ticker)
        sector_data[sector]['count'] += 1
    
    # Add percentages
    for sector in sector_data:
        sector_data[sector]['pct'] = sector_data[sector]['value'] / total_value
    
    return sector_data

def check_entry_limit(ticker, positions, proposed_size=None):
    """
    Check if adding a position would exceed sector limits.
    
    Returns:
        (allowed: bool, message: str, sector: str, current_pct: float, would_be_pct: float)
    """
    sector = get_sector(ticker)
    current_positions = get_open_positions()
    
    # Add proposed position to check
    if proposed_size is None:
        proposed_size = 1  # Default to 1 unit for simulation
    
    test_positions = current_positions.copy()
    if ticker not in test_positions:
        test_positions[ticker] = {'quantity': 0, 'value': 0}
    test_positions[ticker]['value'] += proposed_size
    
    allocation = calculate_sector_allocation(test_positions)
    
    if sector not in allocation:
        return True, f"✅ OK: {sector} sector would be created fresh", sector, 0, 0
    
    current_pct = allocation[sector]['pct']
    
    if current_pct > MAX_SECTOR_ALLOCATION:
        return False, f"❌ BLOCKED: {sector} would be {current_pct*100:.1f}% (limit {MAX_SECTOR_ALLOCATION*100:.0f}%)", sector, current_pct, current_pct
    
    return True, f"✅ OK: {sector} would be {current_pct*100:.1f}%", sector, current_pct, current_pct

def generate_daily_report():
    """Generate daily sector concentration report"""
    positions = get_open_positions()
    
    if not positions:
        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'No open positions',
            'allocation': {},
            'violations': []
        }
    
    allocation = calculate_sector_allocation(positions)
    total_value = sum(p['value'] for p in positions.values())
    
    # Check for violations
    violations = []
    warnings = []
    
    for sector, data in allocation.items():
        pct = data['pct']
        
        if pct > MAX_SECTOR_ALLOCATION:
            violations.append({
                'sector': sector,
                'allocation': pct,
                'limit': MAX_SECTOR_ALLOCATION,
                'excess': pct - MAX_SECTOR_ALLOCATION,
                'tickers': data['tickers'],
                'count': data['count']
            })
        elif pct > ALERT_THRESHOLD:
            warnings.append({
                'sector': sector,
                'allocation': pct,
                'limit': MAX_SECTOR_ALLOCATION,
                'tickers': data['tickers'],
                'count': data['count']
            })
    
    # Calculate effective number of uncorrelated bets
    # Simplified: count distinct sectors with positions
    sectors_in_portfolio = len([s for s in allocation if allocation[s]['pct'] > 0.01])
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_portfolio_value': total_value,
        'allocation': {
            sector: {
                'value': data['value'],
                'allocation': data['pct'],
                'allocation_pct': f"{data['pct']*100:.1f}%",
                'tickers': data['tickers'],
                'count': data['count']
            }
            for sector, data in sorted(allocation.items(), key=lambda x: x[1]['pct'], reverse=True)
        },
        'violations': violations,
        'warnings': warnings,
        'sectors_in_portfolio': sectors_in_portfolio,
        'is_healthy': len(violations) == 0
    }
    
    return report

def save_daily_report(report):
    """Save daily sector report to logs"""
    log_file = LOGS_DIR / 'sector_concentration.json'
    
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
        
        with open(log_file, 'w') as f:
            json.dump(history, f, indent=2)
        
        logger.info(f"Sector report saved: {log_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving sector report: {e}")
        return False

def get_telegram_alert_message(report):
    """Format sector violation alert for Telegram"""
    violations = report.get('violations', [])
    warnings = report.get('warnings', [])
    
    if not violations and not warnings:
        return None
    
    lines = ["🚨 *SECTOR CONCENTRATION ALERT*\n"]
    
    for v in violations:
        lines.append(f"❌ *{v['sector']}*: {v['allocation']*100:.1f}% (limit: 20%)")
        lines.append(f"   {v['count']} tickers: {', '.join(v['tickers'][:3])}")
        if v['count'] > 3:
            lines.append(f"   + {v['count']-3} more")
        lines.append("")
    
    if warnings:
        lines.append("⚠️ *WARNINGS*:")
        for w in warnings:
            lines.append(f"  {w['sector']}: {w['allocation']*100:.1f}%")
    
    return "\n".join(lines)

def main():
    """Run daily sector monitoring"""
    logger.info("=" * 60)
    logger.info("SECTOR CONCENTRATION MONITOR - Daily Check")
    logger.info("=" * 60)
    
    report = generate_daily_report()
    saved = save_daily_report(report)
    
    logger.info(f"\nPortfolio Sectors: {report.get('sectors_in_portfolio', 0)}")
    logger.info(f"Total Value: ${report.get('total_portfolio_value', 0):.2f}")
    
    allocation = report.get('allocation', {})
    if allocation:
        logger.info("\nSector Allocation:")
        for sector in sorted(allocation.keys(), key=lambda s: allocation[s]['allocation'], reverse=True):
            data = allocation[sector]
            pct = data['allocation']
            symbol = "✅" if pct <= MAX_SECTOR_ALLOCATION else "❌"
            logger.info(f"  {symbol} {sector:20s} {pct*100:5.1f}%  ({data['count']} positions)")
    
    violations = report.get('violations', [])
    if violations:
        logger.warning(f"\n⚠️ {len(violations)} SECTOR VIOLATIONS DETECTED:")
        for v in violations:
            excess = (v['excess'] * 100)
            logger.warning(f"   {v['sector']}: {v['allocation']*100:.1f}% (+{excess:.1f}% over limit)")
    
    warnings = report.get('warnings', [])
    if warnings:
        logger.warning(f"\n⚠️ {len(warnings)} EARLY WARNINGS:")
        for w in warnings:
            logger.warning(f"   {w['sector']}: {w['allocation']*100:.1f}%")
    
    if report.get('is_healthy'):
        logger.info("\n✅ Portfolio is healthy - no sector violations")
    
    return 0 if report.get('is_healthy') else 1

if __name__ == '__main__':
    sys.exit(main())
