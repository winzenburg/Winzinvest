#!/usr/bin/env python3
"""
Box Strategy Screener (stub)
- Finds consolidation boxes with reasonable range and TTM Squeeze-like condition.
- Safe: prints + CSV only.
TODO: Confirm box lookback window, range %, and squeeze parameters with Ryan.
"""
import sys
import json
import pandas as pd
try:
    import yfinance as yf  # type: ignore
except Exception as e:
    print("Missing dependency: yfinance (pip install yfinance)")
    sys.exit(1)

DEFAULT_WATCHLIST = ["AFRM","UPST","COIN","HOOD","SOFI"]

LOOKBACK = 20
MAX_RANGE = 0.15  # 15%


def screen(tickers, lookback=LOOKBACK):
    rows = []
    for t in tickers:
        try:
            data = yf.download(t, period="3mo", progress=False)
            if len(data) < lookback:
                continue
            recent = data.iloc[-lookback:]
            box_high = float(recent["High"].max())
            box_low = float(recent["Low"].min())
            box_range = (box_high - box_low) / max(box_low, 1e-9)
            if box_range > MAX_RANGE:
                continue
            # crude squeeze proxy using Bollinger vs Keltner
            data["20_MA"] = data["Close"].rolling(20).mean()
            data["20_STD"] = data["Close"].rolling(20).std()
            data["Upper_BB"] = data["20_MA"] + 2 * data["20_STD"]
            data["Lower_BB"] = data["20_MA"] - 2 * data["20_STD"]
            data["Upper_KC"] = data["20_MA"] + 1.5 * data["20_STD"]
            data["Lower_KC"] = data["20_MA"] - 1.5 * data["20_STD"]
            squeeze_on = (data["Lower_BB"] > data["Lower_KC"]) & (data["Upper_BB"] < data["Upper_KC"])
            if not bool(squeeze_on.iloc[-1]):
                continue
            rows.append({
                "Ticker": t,
                "Price": round(float(data.iloc[-1]["Close"]), 2),
                "BoxHigh": round(box_high, 2),
                "BoxLow": round(box_low, 2),
                "BoxRangePct": round(box_range * 100, 2),
            })
        except Exception as e:
            print(f"WARN: {t}: {e}")
    return pd.DataFrame(rows)

if __name__ == "__main__":
    tickers = DEFAULT_WATCHLIST
    if len(sys.argv) > 1:
        try:
            tickers = json.loads(sys.argv[1])
        except Exception:
            pass
    df = screen(tickers)
    print(df)
    df.to_csv("box_candidates.csv", index=False)
    print("Wrote box_candidates.csv")
