#!/usr/bin/env python3
import sys
from pathlib import Path
# Ensure workspace root is on path
sys.path.append(str(Path(__file__).resolve().parents[2]))
from trading.scripts import midday_scan as ms

def main():
    tickers = ms.load_watchlist()
    out = []
    for t in tickers:
        try:
            df = ms.get_intraday(t)
            if df is None or df.empty:
                continue
            last_close = float(df.iloc[-1]['Close'])
            sigs = ms.scan_ticker(t)
            for tkr, level, pattern, action in sigs:
                out.append((tkr, last_close, level, pattern, action))
        except Exception as e:
            print(f"WARN {t}: {e}", file=sys.stderr)
            continue
    # priority sort same as midday_scan
    priority_order = {
        'Midday Reversal Down': 1,
        'Midday Reversal Up': 1,
        'Range Breakout': 2,
        'Range Breakdown': 2,
        'Volume Spike': 3,
        'Momentum ↑': 4,
        'Momentum ↓': 4,
        'Retest R': 5,
        'Retest S': 5,
        'VWAP Test': 6,
    }
    out_sorted = sorted(out, key=lambda x: (priority_order.get(x[3], 9), x[0]))
    for tkr, price, level, pattern, action in out_sorted:
        # Map pattern/action to requested concise format
        # Key Level: use level value; Signal: pattern + action description
        print(f"{tkr}: [{price:.2f}] | Key Level: {level} | Signal: {pattern} — {action}")

if __name__ == '__main__':
    main()
