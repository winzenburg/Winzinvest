#!/usr/bin/env python3
"""
Conservative Strategy Screener (stub)
- High-quality dividend payers with sustainable payouts and reasonable valuation.
- Safe: prints results to stdout and writes CSV locally; no network posts.
TODO: Confirm exact thresholds with Ryan before production use.
"""
import sys
import json
import pandas as pd
try:
    import yfinance as yf  # type: ignore
except Exception as e:
    print("Missing dependency: yfinance (pip install yfinance)")
    sys.exit(1)

DEFAULT_TICKERS = ["AAPL","MSFT","JPM","JNJ","PG","XOM","CVX"]

# Threshold defaults (edit as needed)
THRESHOLDS = {
    "min_market_cap": 10_000_000_000,  # $10B
    "min_dividend_yield": 0.02,
    "max_dividend_yield": 0.06,
    "max_payout_ratio": 0.70,
    "max_pe": 25.0,
}

def screen(tickers):
    rows = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            mc = info.get("marketCap") or 0
            dy = info.get("dividendYield") or 0
            pr = info.get("payoutRatio") or 1
            pe = info.get("trailingPE") or 999
            fwd_eps = info.get("forwardEps") or 0
            tr_eps = info.get("trailingEps") or 0
            if mc < THRESHOLDS["min_market_cap"]: continue
            if not (THRESHOLDS["min_dividend_yield"] < dy < THRESHOLDS["max_dividend_yield"]): continue
            if pr > THRESHOLDS["max_payout_ratio"]: continue
            if pe > THRESHOLDS["max_pe"]: continue
            if fwd_eps < tr_eps: continue
            rows.append({
                "Ticker": t,
                "Name": info.get("shortName"),
                "Yield": f"{dy*100:.2f}%",
                "P/E": f"{pe:.2f}",
                "Payout": f"{pr*100:.2f}%",
                "MarketCap": mc,
            })
        except Exception as e:
            print(f"WARN: {t}: {e}")
    return pd.DataFrame(rows)

if __name__ == "__main__":
    tickers = DEFAULT_TICKERS
    if len(sys.argv) > 1:
        # allow a JSON list via argv[1]
        try:
            tickers = json.loads(sys.argv[1])
        except Exception:
            pass
    df = screen(tickers)
    print(df)
    df.to_csv("conservative_candidates.csv", index=False)
    print("Wrote conservative_candidates.csv")
