#!/usr/bin/env python3
"""
Trend Following Screener (stub)
- Finds strong uptrends using MA50/MA200 + MACD signal cross + distance from 52w low.
- Safe: prints + CSV only.
TODO: Confirm exact indicator windows and thresholds with Ryan.
"""
import sys
import json
import pandas as pd
try:
    import yfinance as yf  # type: ignore
except Exception as e:
    print("Missing dependency: yfinance (pip install yfinance)")
    sys.exit(1)

DEFAULT_WATCHLIST = ["NVDA","AMD","SMCI","DELL","PLTR","TSLA"]

def screen(tickers):
    out = []
    for t in tickers:
        try:
            data = yf.download(t, period="1y", progress=False)
            if data.empty:
                continue
            data["MA50"] = data["Close"].rolling(50).mean()
            data["MA200"] = data["Close"].rolling(200).mean()
            ema12 = data["Close"].ewm(span=12, adjust=False).mean()
            ema26 = data["Close"].ewm(span=26, adjust=False).mean()
            data["MACD"] = ema12 - ema26
            data["Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()
            latest = data.iloc[-1]
            conds = [
                latest["Close"] > latest["MA50"],
                latest["Close"] > latest["MA200"],
                latest["MA50"] > latest["MA200"],
                latest["MACD"] > latest["Signal"],
            ]
            if not all(conds):
                continue
            low_52w = data["Close"].min()
            if latest["Close"] <= low_52w * 1.3:
                continue
            out.append({
                "Ticker": t,
                "Price": round(float(latest["Close"]), 2),
                "MA50": round(float(latest["MA50"]), 2),
                "MA200": round(float(latest["MA200"]), 2),
                "MACD_minus_Signal": round(float(latest["MACD"] - latest["Signal"]), 3),
            })
        except Exception as e:
            print(f"WARN: {t}: {e}")
    return pd.DataFrame(out)

if __name__ == "__main__":
    tickers = DEFAULT_WATCHLIST
    if len(sys.argv) > 1:
        try:
            tickers = json.loads(sys.argv[1])
        except Exception:
            pass
    df = screen(tickers)
    print(df)
    df.to_csv("trend_candidates.csv", index=False)
    print("Wrote trend_candidates.csv")
