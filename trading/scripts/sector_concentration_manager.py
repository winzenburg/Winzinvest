#!/usr/bin/env python3
"""
Sector Concentration Manager
Enforces: Max 1 position per sector
Reduces correlation risk and diversifies trading portfolio
"""

import json
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Sector classification (symbol → sector)
SECTOR_MAP = {
    # Technology
    'AAPL': 'Technology', 'MSFT': 'Technology', 'NVDA': 'Technology', 'GOOGL': 'Technology',
    'META': 'Technology', 'INTC': 'Technology', 'AMD': 'Technology', 'AVGO': 'Technology',
    'QCOM': 'Technology', 'ASML': 'Technology', 'NXPI': 'Technology', 'MCHP': 'Technology',
    'LRCX': 'Technology', 'KLA': 'Technology', 'AMAT': 'Technology', 'CRWD': 'Technology',
    'NET': 'Technology', 'DDOG': 'Technology', 'OKTA': 'Technology', 'SNOW': 'Technology',
    'CRM': 'Technology', 'NOW': 'Technology', 'ADBE': 'Technology', 'CSCO': 'Technology',
    'INTU': 'Technology', 'PAYC': 'Technology', 'SNPS': 'Technology', 'CDNS': 'Technology',
    'SPLK': 'Technology', 'TWLO': 'Technology', 'ZM': 'Technology', 'TEAM': 'Technology',
    'RBLX': 'Technology', 'U': 'Technology', 'DASH': 'Technology', 'COIN': 'Technology',
    
    # Financials
    'JPM': 'Financials', 'BAC': 'Financials', 'WFC': 'Financials', 'GS': 'Financials',
    'MS': 'Financials', 'BLK': 'Financials', 'HOOD': 'Financials', 'SOFI': 'Financials',
    'PYPL': 'Financials', 'SQ': 'Financials', 'ICL': 'Financials', 'APO': 'Financials',
    'KKR': 'Financials', 'BX': 'Financials', 'ARES': 'Financials', 'TPG': 'Financials',
    'SCHW': 'Financials', 'IBKR': 'Financials', 'TROW': 'Financials', 'ONYX': 'Financials',
    
    # Energy
    'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'MPC': 'Energy', 'PSX': 'Energy',
    'VLO': 'Energy', 'HES': 'Energy', 'EOG': 'Energy', 'FANG': 'Energy', 'OKE': 'Energy',
    'GEVO': 'Energy', 'PLUG': 'Energy', 'FCEL': 'Energy',
    
    # Healthcare
    'JNJ': 'Healthcare', 'UNH': 'Healthcare', 'PFE': 'Healthcare', 'ABBV': 'Healthcare',
    'TMO': 'Healthcare', 'ISRG': 'Healthcare', 'DXCM': 'Healthcare', 'VEEV': 'Healthcare',
    'TDOC': 'Healthcare', 'GILD': 'Healthcare', 'BIIB': 'Healthcare', 'REGN': 'Healthcare',
    'VRTX': 'Healthcare', 'ALXN': 'Healthcare', 'MRK': 'Healthcare', 'LLY': 'Healthcare',
    
    # Industrials
    'CAT': 'Industrials', 'BA': 'Industrials', 'HON': 'Industrials', 'ITW': 'Industrials',
    'GE': 'Industrials', 'MMM': 'Industrials', 'RTX': 'Industrials', 'LUV': 'Industrials',
    'UAL': 'Industrials', 'DAL': 'Industrials', 'ALK': 'Industrials', 'WAB': 'Industrials',
    'UNP': 'Industrials', 'CSX': 'Industrials', 'KSU': 'Industrials',
    
    # Consumer Discretionary
    'AMZN': 'Consumer Discretionary', 'TSLA': 'Consumer Discretionary', 'MCD': 'Consumer Discretionary',
    'NKE': 'Consumer Discretionary', 'SBUX': 'Consumer Discretionary', 'TJX': 'Consumer Discretionary',
    'RCL': 'Consumer Discretionary', 'CCL': 'Consumer Discretionary', 'ROST': 'Consumer Discretionary',
    'DKS': 'Consumer Discretionary', 'ULTA': 'Consumer Discretionary',
    
    # Consumer Staples
    'WMT': 'Consumer Staples', 'PG': 'Consumer Staples', 'KO': 'Consumer Staples',
    'PEP': 'Consumer Staples', 'MO': 'Consumer Staples', 'PM': 'Consumer Staples',
    'GIS': 'Consumer Staples', 'ADM': 'Consumer Staples', 'MKC': 'Consumer Staples',
    
    # Real Estate
    'SPG': 'Real Estate', 'DLR': 'Real Estate', 'PSA': 'Real Estate', 'ARE': 'Real Estate',
    'WELL': 'Real Estate', 'PLD': 'Real Estate', 'VICI': 'Real Estate', 'COIN': 'Real Estate',
    
    # Utilities
    'NEE': 'Utilities', 'DUK': 'Utilities', 'SO': 'Utilities', 'EXC': 'Utilities',
    'AES': 'Utilities', 'PEG': 'Utilities', 'ES': 'Utilities', 'EIX': 'Utilities',
    
    # Materials
    'NEM': 'Materials', 'FCX': 'Materials', 'TECK': 'Materials', 'ALB': 'Materials',
    'LIN': 'Materials', 'SHW': 'Materials', 'APD': 'Materials', 'ECL': 'Materials',
    'DOW': 'Materials', 'LYB': 'Materials',
    
    # Communication Services
    'NFLX': 'Communication Services', 'DIS': 'Communication Services', 'PARA': 'Communication Services',
    'FOXA': 'Communication Services', 'FOX': 'Communication Services', 'CMCSA': 'Communication Services',
    'CHTR': 'Communication Services', 'ATUS': 'Communication Services', 'PINS': 'Communication Services',
    'SNAP': 'Communication Services', 'ROKU': 'Communication Services', 'TTD': 'Communication Services',
    'MOMO': 'Communication Services', 'BILI': 'Communication Services', 'IQ': 'Communication Services',
}

def get_sector(symbol: str) -> str:
    """Get sector for a symbol. Returns 'Unknown' if not classified."""
    return SECTOR_MAP.get(symbol.upper(), 'Unknown')

def get_position_sectors(positions: list) -> dict:
    """
    Map positions to sectors.
    
    Args:
        positions: List of position dicts with 'symbol', 'quantity'
    
    Returns: Dict { sector: [symbols...] }
    """
    sector_map = {}
    for pos in positions:
        if pos['quantity'] == 0:
            continue
        symbol = pos['symbol']
        sector = get_sector(symbol)
        if sector not in sector_map:
            sector_map[sector] = []
        sector_map[sector].append(symbol)
    
    return sector_map

def check_sector_limit(positions: list, max_per_sector: int = 1) -> dict:
    """
    Check sector concentration limits.
    
    Args:
        positions: List of position dicts
        max_per_sector: Max positions per sector (default: 1)
    
    Returns: {
        'compliant': bool,
        'violations': [{ sector, count, symbols }],
        'at_limit': [sectors with exactly max_per_sector],
    }
    """
    sector_map = get_position_sectors(positions)
    
    violations = []
    at_limit = []
    
    for sector, symbols in sector_map.items():
        if len(symbols) > max_per_sector:
            violations.append({
                'sector': sector,
                'count': len(symbols),
                'symbols': symbols,
                'excess': len(symbols) - max_per_sector,
            })
        elif len(symbols) == max_per_sector:
            at_limit.append(sector)
    
    return {
        'compliant': len(violations) == 0,
        'violations': violations,
        'at_limit': at_limit,
        'sector_counts': {s: len(syms) for s, syms in sector_map.items()},
    }

def can_add_position(symbol: str, positions: list, max_per_sector: int = 1) -> dict:
    """
    Check if new position can be added without violating sector limit.
    
    Args:
        symbol: Symbol to add
        positions: Current positions
        max_per_sector: Max per sector
    
    Returns: {
        'allowed': bool,
        'reason': str,
        'sector': str,
        'current_in_sector': int,
    }
    """
    sector = get_sector(symbol)
    current_positions = [p for p in positions if get_sector(p['symbol']) == sector and p['quantity'] > 0]
    count = len(current_positions)
    
    if count >= max_per_sector:
        return {
            'allowed': False,
            'reason': f'Sector "{sector}" already at limit ({max_per_sector}): {[p["symbol"] for p in current_positions]}',
            'sector': sector,
            'current_in_sector': count,
        }
    
    return {
        'allowed': True,
        'reason': f'Sector "{sector}" has {count}/{max_per_sector} positions',
        'sector': sector,
        'current_in_sector': count,
    }

def recommend_closes(positions: list, max_per_sector: int = 1) -> dict:
    """
    Recommend which positions to close to comply with sector limits.
    
    Args:
        positions: List of positions with 'symbol', 'quantity', 'entry_price', 'current_price'
        max_per_sector: Max per sector
    
    Returns: {
        'violations': [{ sector, must_close, recommendation }],
        'priority': [(symbol, reason)],
    }
    """
    sector_map = get_position_sectors(positions)
    violations = []
    priority = []
    
    for sector, symbols in sector_map.items():
        if len(symbols) > max_per_sector:
            # Determine which to close (keep best performers, close worst)
            symbol_perf = []
            for sym in symbols:
                pos = next((p for p in positions if p['symbol'] == sym), None)
                if pos:
                    gain = ((pos.get('current_price', pos.get('entry_price', 0)) - pos.get('entry_price', 0)) / 
                            pos.get('entry_price', 1) * 100) if pos.get('entry_price', 0) > 0 else 0
                    symbol_perf.append((sym, gain))
            
            symbol_perf.sort(key=lambda x: x[1], reverse=True)  # Sort by gain
            must_close = [s[0] for s in symbol_perf[max_per_sector:]]  # Close worst performers
            
            violations.append({
                'sector': sector,
                'current': len(symbols),
                'allowed': max_per_sector,
                'must_close': must_close,
                'must_close_count': len(must_close),
                'keep': symbols[:max_per_sector],
            })
            
            for symbol in must_close:
                priority.append((symbol, f'Sector "{sector}" violation: {len(symbols)} positions, limit {max_per_sector}'))
    
    return {
        'compliant': len(violations) == 0,
        'violations': violations,
        'priority_closes': priority,
    }

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    test_positions = [
        {'symbol': 'AAPL', 'quantity': 100, 'entry_price': 180, 'current_price': 185},
        {'symbol': 'MSFT', 'quantity': 50, 'entry_price': 400, 'current_price': 410},
        {'symbol': 'NVDA', 'quantity': 75, 'entry_price': 700, 'current_price': 750},
        {'symbol': 'JPM', 'quantity': 200, 'entry_price': 150, 'current_price': 160},
        {'symbol': 'GS', 'quantity': 100, 'entry_price': 400, 'current_price': 410},
    ]
    
    print("\n=== Test: Sector Concentration Check ===")
    result = check_sector_limit(test_positions, max_per_sector=1)
    print(f"Compliant: {result['compliant']}")
    print(f"Sector counts: {result['sector_counts']}")
    
    print("\n=== Test: Can Add Position? ===")
    can_add = can_add_position('AMD', test_positions)
    print(f"Can add AMD? {can_add['allowed']}")
    print(f"Reason: {can_add['reason']}")
    
    print("\n=== Test: Recommend Closes ===")
    recommends = recommend_closes(test_positions, max_per_sector=1)
    print(f"Compliant: {recommends['compliant']}")
    for v in recommends['violations']:
        print(f"\nSector: {v['sector']}")
        print(f"  Current: {v['current']}, Allowed: {v['allowed']}")
        print(f"  Keep: {v['keep']}")
        print(f"  Close: {v['must_close']}")
