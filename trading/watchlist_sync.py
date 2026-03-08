#!/usr/bin/env python3
"""
TradingView Screener → Watchlist Sync
Imports screener CSV output and syncs with local watchlist.json
"""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WATCHLIST_FILE = Path(os.path.expanduser('~/.openclaw/workspace/trading/watchlist.json'))
SCREENER_EXPORT_DIR = Path(os.path.expanduser('~/.openclaw/workspace/trading/screener_exports'))


class Watchlist:
    """Manage swing trading watchlist"""
    
    def __init__(self, filepath: Path = WATCHLIST_FILE):
        self.filepath = filepath
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load watchlist from JSON"""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading watchlist: {e}")
                return self._new_watchlist()
        else:
            logger.info(f"Creating new watchlist at {self.filepath}")
            return self._new_watchlist()
    
    def _new_watchlist(self) -> Dict:
        """Create new watchlist structure"""
        return {
            'name': 'Swing Trading Watchlist',
            'created': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'stocks': [],
            'metadata': {
                'total_added': 0,
                'total_removed': 0,
                'screener_runs': 0
            }
        }
    
    def add_stock(self, symbol: str, reason: str = '', **kwargs) -> bool:
        """Add stock to watchlist (avoid duplicates)"""
        # Check if already exists
        if any(s['symbol'] == symbol for s in self.data['stocks']):
            logger.info(f"⏭️  {symbol} already in watchlist")
            return False
        
        stock = {
            'symbol': symbol,
            'added': datetime.now().isoformat(),
            'reason': reason,
            'status': 'watching',
            **kwargs
        }
        
        self.data['stocks'].append(stock)
        logger.info(f"✅ Added {symbol} to watchlist")
        self.data['metadata']['total_added'] += 1
        return True
    
    def remove_stock(self, symbol: str) -> bool:
        """Remove stock from watchlist"""
        initial_count = len(self.data['stocks'])
        self.data['stocks'] = [s for s in self.data['stocks'] if s['symbol'] != symbol]
        
        if len(self.data['stocks']) < initial_count:
            logger.info(f"✅ Removed {symbol} from watchlist")
            self.data['metadata']['total_removed'] += 1
            return True
        return False
    
    def update_stock(self, symbol: str, **kwargs) -> bool:
        """Update stock metadata"""
        for stock in self.data['stocks']:
            if stock['symbol'] == symbol:
                stock.update(kwargs)
                stock['last_updated'] = datetime.now().isoformat()
                logger.info(f"✅ Updated {symbol}")
                return True
        return False
    
    def get_stock(self, symbol: str) -> Dict:
        """Get stock by symbol"""
        for stock in self.data['stocks']:
            if stock['symbol'] == symbol:
                return stock
        return None
    
    def list_stocks(self) -> List[Dict]:
        """List all stocks in watchlist"""
        return sorted(self.data['stocks'], key=lambda x: x.get('added', ''), reverse=True)
    
    def save(self):
        """Save watchlist to JSON"""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self.data['last_updated'] = datetime.now().isoformat()
            
            with open(self.filepath, 'w') as f:
                json.dump(self.data, f, indent=2)
            
            logger.info(f"✅ Watchlist saved ({len(self.data['stocks'])} stocks)")
        except Exception as e:
            logger.error(f"Error saving watchlist: {e}")
    
    def import_csv(self, csv_file: Path) -> int:
        """Import stocks from TradingView screener CSV"""
        if not csv_file.exists():
            logger.error(f"CSV file not found: {csv_file}")
            return 0
        
        added = 0
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # TradingView CSV has columns like: Symbol, Name, Close, Volume, RSI, etc.
                    symbol = row.get('Symbol', '').strip()
                    
                    if not symbol:
                        continue
                    
                    reason = f"Screener export from {csv_file.name}"
                    
                    if self.add_stock(
                        symbol=symbol,
                        reason=reason,
                        name=row.get('Name', ''),
                        price=row.get('Close', ''),
                        volume=row.get('Volume', ''),
                        rsi=row.get('RSI', ''),
                        relative_strength=row.get('RelStr', '')
                    ):
                        added += 1
            
            logger.info(f"✅ Imported {added} new stocks from {csv_file.name}")
            self.data['metadata']['screener_runs'] += 1
            
        except Exception as e:
            logger.error(f"Error importing CSV: {e}")
        
        return added
    
    def format_report(self) -> str:
        """Format watchlist as readable report"""
        stocks = self.list_stocks()
        
        report = f"""
╔═══════════════════════════════════════════════════════════╗
║            SWING TRADING WATCHLIST
║            {len(stocks)} stocks being monitored
╚═══════════════════════════════════════════════════════════╝

"""
        
        if stocks:
            report += f"{'Symbol':<10} {'Price':<10} {'RSI':<8} {'Rel Str':<10} {'Added':<20} {'Status':<12}\n"
            report += "─" * 70 + "\n"
            
            for stock in stocks:
                price = stock.get('price', '—')
                rsi = stock.get('rsi', '—')
                rel_str = stock.get('relative_strength', '—')
                added = stock.get('added', '')[:10]
                status = stock.get('status', 'watching')
                
                report += f"{stock['symbol']:<10} {str(price):<10} {str(rsi):<8} {str(rel_str):<10} {added:<20} {status:<12}\n"
        else:
            report += "No stocks in watchlist.\n"
        
        report += "\n" + "═" * 70 + "\n"
        return report


def main():
    """Main execution"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: watchlist_sync.py [command] [args]")
        print("\nCommands:")
        print("  add <SYMBOL> [reason]    - Add stock to watchlist")
        print("  remove <SYMBOL>          - Remove stock from watchlist")
        print("  list                     - List all stocks")
        print("  import <CSV_FILE>        - Import from TradingView screener CSV")
        print("  report                   - Print watchlist report")
        exit(1)
    
    watchlist = Watchlist()
    command = sys.argv[1].lower()
    
    if command == 'add' and len(sys.argv) >= 3:
        symbol = sys.argv[2].upper()
        reason = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else ''
        watchlist.add_stock(symbol, reason)
        watchlist.save()
    
    elif command == 'remove' and len(sys.argv) >= 3:
        symbol = sys.argv[2].upper()
        watchlist.remove_stock(symbol)
        watchlist.save()
    
    elif command == 'list':
        print(watchlist.format_report())
    
    elif command == 'import' and len(sys.argv) >= 3:
        csv_file = Path(sys.argv[2])
        watchlist.import_csv(csv_file)
        watchlist.save()
        print(watchlist.format_report())
    
    elif command == 'report':
        print(watchlist.format_report())
    
    else:
        print(f"Unknown command: {command}")
        exit(1)


if __name__ == '__main__':
    main()
