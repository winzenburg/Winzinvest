#!/usr/bin/env python3
"""
Daily Options Positions Email
==============================
Generates a styled HTML email of all current options positions and sends
it via Resend.  Designed to run in the pre-close scheduler slot alongside
daily_portfolio_report.py.

Usage:
  python3 daily_options_email.py           # generate + send
  python3 daily_options_email.py --preview  # write HTML to /tmp and skip send
"""

import json
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR    = TRADING_DIR / "logs"
REPORT_PATH = TRADING_DIR / "docs" / "OPTIONS_POSITIONS.md"

LOGS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

# Load .env so IB_PORT and TRADING_MODE are always current
_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "daily_options_email.log"),
    ],
)
log = logging.getLogger(__name__)

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
IB_CLIENT_ID = 197

# ── Data collection ──────────────────────────────────────────────────────────

def _fetch_account(ib: Any) -> dict[str, float]:
    tags = {"NetLiquidation", "TotalCashValue", "GrossPositionValue",
            "AvailableFunds", "BuyingPower"}
    return {
        v.tag: float(v.value)
        for v in ib.accountSummary()
        if v.tag in tags and v.currency == "USD"
    }


def _fetch_options(ib: Any) -> list[dict]:
    rows: list[dict] = []
    for pos in ib.positions():
        c = pos.contract
        if c.secType != "OPT" or pos.position == 0:
            continue
        rows.append({
            "symbol":   c.symbol,
            "strike":   c.strike,
            "right":    c.right,
            "expiry":   c.lastTradeDateOrContractMonth,
            "qty":      int(pos.position),
            "avg_cost": float(pos.avgCost),
            "mult":     int(c.multiplier) if c.multiplier else 100,
        })
    return rows


def _fetch_prices(symbols: list[str]) -> dict[str, float]:
    import yfinance as yf
    prices: dict[str, float] = {}
    for sym in symbols:
        try:
            h = yf.download(sym, period="2d", progress=False, auto_adjust=True)
            if h.empty:
                continue
            cl = h["Close"]
            if hasattr(cl, "columns"):
                cl = cl.iloc[:, 0]
            prices[sym] = round(float(cl.iloc[-1]), 2)
        except Exception:
            pass
    return prices


# ── Enrichment ────────────────────────────────────────────────────────────────

def _enrich(opts: list[dict], prices: dict[str, float]) -> list[dict]:
    today = date.today()
    enriched: list[dict] = []
    for o in opts:
        exp_date = datetime.strptime(o["expiry"], "%Y%m%d").date()
        dte = (exp_date - today).days
        spot = prices.get(o["symbol"], 0)
        strike = o["strike"]
        qty = o["qty"]

        if spot > 0:
            otm_pct = ((strike - spot) / spot * 100) if o["right"] == "C" \
                      else ((spot - strike) / spot * 100)
            moneyness = f"OTM {otm_pct:.1f}%" if otm_pct >= 0 else f"ITM {abs(otm_pct):.1f}%"
        else:
            otm_pct = None
            moneyness = "N/A"

        premium_per = abs(o["avg_cost"])
        total_prem = premium_per * abs(qty)

        if o["right"] == "C" and qty < 0:
            otype = "Covered Call"
        elif o["right"] == "P" and qty < 0:
            otype = "CSP"
        elif o["right"] == "C" and qty > 0:
            otype = "Long Call"
        else:
            otype = "Long Put"

        assign_risk = abs(qty) * strike * 100 if (o["right"] == "P" and qty < 0) else None

        compliant = True
        flag = ""
        if qty < 0:
            if otm_pct is not None and otm_pct < 10:
                compliant = False
                flag = f"{otm_pct:.1f}% OTM"
            if dte < 21 or dte > 45:
                compliant = False
                flag = f"DTE {dte}"

        enriched.append({
            "symbol": o["symbol"], "type": otype, "right": o["right"],
            "strike": strike, "expiry_str": exp_date.strftime("%b %d"),
            "dte": dte, "qty": qty, "spot": spot, "moneyness": moneyness,
            "otm_pct": otm_pct, "prem_per": premium_per,
            "total_prem": total_prem, "assign_risk": assign_risk,
            "compliant": compliant, "flag": flag,
        })
    return enriched


# ── HTML generation ──────────────────────────────────────────────────────────

_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       color: #1a1a2e; background: #f0f2f5; margin: 0; padding: 20px; }
.wrap { max-width: 860px; margin: 0 auto; background: #fff; border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0,0,0,.08); overflow: hidden; }
.hdr  { background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        color: #fff; padding: 28px 32px 22px; }
.hdr h1 { margin: 0 0 6px; font-size: 22px; letter-spacing: -.3px; }
.hdr p  { margin: 0; opacity: .75; font-size: 13px; }
.body { padding: 28px 32px 36px; }
.kpi-row { display: flex; gap: 14px; margin-bottom: 24px; flex-wrap: wrap; }
.kpi { flex: 1; min-width: 130px; background: #f8f9fb; border-radius: 8px;
       padding: 14px 16px; text-align: center; }
.kpi .val { font-size: 20px; font-weight: 700; color: #0f2027; }
.kpi .lbl { font-size: 11px; color: #6c757d; text-transform: uppercase; letter-spacing: .5px; margin-top: 2px; }
h2 { font-size: 15px; color: #2c5364; margin: 28px 0 10px; border-bottom: 2px solid #e9ecef; padding-bottom: 6px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #f1f3f5; padding: 8px 10px; text-align: left; font-weight: 600;
     color: #495057; border-bottom: 2px solid #dee2e6; font-size: 11px; text-transform: uppercase; letter-spacing: .4px; }
td { padding: 7px 10px; border-bottom: 1px solid #f1f3f5; }
tr:hover td { background: #f8f9fa; }
.r  { text-align: right; }
.ok { color: #2e7d32; } .warn { color: #e65100; } .bad { color: #c62828; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.pill-ok   { background: #e8f5e9; color: #2e7d32; }
.pill-warn { background: #fff3e0; color: #e65100; }
.pill-bad  { background: #ffebee; color: #c62828; }
.exp-group { margin-bottom: 18px; }
.ft { padding: 18px 32px; background: #f8f9fb; color: #adb5bd; font-size: 11px; text-align: center; }
"""


def _pill(compliant: bool, flag: str) -> str:
    if compliant:
        return '<span class="pill pill-ok">OK</span>'
    return f'<span class="pill pill-warn">{flag}</span>'


def _money(v: float) -> str:
    return f"${v:,.0f}"


def build_html(acct: dict[str, float], enriched: list[dict]) -> str:
    now_str = datetime.now().strftime("%A, %B %d, %Y &middot; %I:%M %p MT")
    nlv  = acct.get("NetLiquidation", 0)
    cash = acct.get("TotalCashValue", 0)
    gpv  = acct.get("GrossPositionValue", 0)

    cc  = sorted([r for r in enriched if r["type"] == "Covered Call"], key=lambda x: x["symbol"])
    csp = sorted([r for r in enriched if r["type"] == "CSP"],          key=lambda x: x["symbol"])
    longs = sorted([r for r in enriched if r["qty"] > 0],              key=lambda x: (x["dte"], x["symbol"]))

    total_cc  = sum(r["total_prem"] for r in cc)
    total_csp = sum(r["total_prem"] for r in csp)
    total     = total_cc + total_csp
    n_short   = sum(abs(r["qty"]) for r in cc + csp)
    avg_dte   = sum(r["dte"] for r in cc + csp) / len(cc + csp) if cc + csp else 0
    annual    = total * (365 / avg_dte) if avg_dte > 0 else 0
    assign    = sum(r["assign_risk"] for r in csp if r["assign_risk"])
    flagged   = [r for r in cc + csp if not r["compliant"]]
    leverage  = gpv / nlv if nlv else 0

    # Expiration calendar
    from collections import defaultdict
    exp_groups: dict[str, list[dict]] = defaultdict(list)
    for r in cc + csp:
        exp_groups[r["expiry_str"]].append(r)

    def _opt_table(rows: list[dict], show_assign: bool = False) -> str:
        cols = "<tr><th>Symbol</th><th>Strike</th><th>Expiry</th><th class='r'>DTE</th>" \
               "<th class='r'>Spot</th><th>Moneyness</th><th class='r'>Qty</th>" \
               "<th class='r'>Premium</th>"
        if show_assign:
            cols += "<th class='r'>Assign Risk</th>"
        cols += "<th>Status</th></tr>"
        body = ""
        for r in rows:
            right_lbl = "C" if r["right"] == "C" else "P"
            body += (
                f"<tr><td><strong>{r['symbol']}</strong></td>"
                f"<td>${r['strike']:.0f} {right_lbl}</td>"
                f"<td>{r['expiry_str']}</td>"
                f"<td class='r'>{r['dte']}d</td>"
                f"<td class='r'>${r['spot']:,.2f}</td>"
                f"<td>{r['moneyness']}</td>"
                f"<td class='r'>&times;{abs(r['qty'])}</td>"
                f"<td class='r'>{_money(r['total_prem'])}</td>"
            )
            if show_assign:
                body += f"<td class='r'>{_money(r['assign_risk']) if r['assign_risk'] else '—'}</td>"
            body += f"<td>{_pill(r['compliant'], r['flag'])}</td></tr>"
        return f"<table>{cols}{body}</table>"

    # Build sections
    cc_html  = _opt_table(cc) if cc else "<p>No covered calls.</p>"
    csp_html = _opt_table(csp, show_assign=True) if csp else "<p>No CSPs.</p>"

    longs_html = ""
    if longs:
        longs_html = "<h2>Long Options</h2><table>"
        longs_html += "<tr><th>Symbol</th><th>Strike</th><th>Expiry</th><th class='r'>DTE</th><th class='r'>Spot</th><th>Moneyness</th><th class='r'>Qty</th><th>Note</th></tr>"
        for r in longs:
            right_lbl = "C" if r["right"] == "C" else "P"
            note = "Expires tomorrow" if r["dte"] <= 1 else ""
            longs_html += (
                f"<tr><td><strong>{r['symbol']}</strong></td>"
                f"<td>${r['strike']:.0f} {right_lbl}</td>"
                f"<td>{r['expiry_str']}</td>"
                f"<td class='r'>{r['dte']}d</td>"
                f"<td class='r'>${r['spot']:,.2f}</td>"
                f"<td>{r['moneyness']}</td>"
                f"<td class='r'>&times;{r['qty']}</td>"
                f"<td style='color:#6c757d'>{note}</td></tr>"
            )
        longs_html += "</table>"

    flags_html = ""
    if flagged:
        flags_html = "<h2>Action Items</h2><table>"
        flags_html += "<tr><th>Symbol</th><th>Type</th><th>Strike</th><th>Issue</th></tr>"
        for r in sorted(flagged, key=lambda x: x.get("otm_pct") or 999):
            right_lbl = "C" if r["right"] == "C" else "P"
            flags_html += (
                f"<tr><td><strong>{r['symbol']}</strong></td>"
                f"<td>{r['type']}</td>"
                f"<td>${r['strike']:.0f} {right_lbl}</td>"
                f"<td class='warn'>{r['flag']}</td></tr>"
            )
        flags_html += "</table>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CSS}</style></head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>Options Positions Report</h1>
    <p>{now_str}</p>
  </div>
  <div class="body">

    <div class="kpi-row">
      <div class="kpi"><div class="val">{_money(total)}</div><div class="lbl">Premium Collected</div></div>
      <div class="kpi"><div class="val">{_money(annual)}</div><div class="lbl">Annual Run-Rate</div></div>
      <div class="kpi"><div class="val">{n_short}</div><div class="lbl">Short Contracts</div></div>
      <div class="kpi"><div class="val">{avg_dte:.0f}d</div><div class="lbl">Avg DTE</div></div>
      <div class="kpi"><div class="val">{leverage:.2f}&times;</div><div class="lbl">Leverage</div></div>
    </div>

    <div class="kpi-row">
      <div class="kpi"><div class="val">{_money(nlv)}</div><div class="lbl">NLV</div></div>
      <div class="kpi"><div class="val">{_money(cash)}</div><div class="lbl">Cash</div></div>
      <div class="kpi"><div class="val">{_money(assign)}</div><div class="lbl">CSP Obligation</div></div>
      <div class="kpi"><div class="val">{len(flagged)}</div><div class="lbl">Flags</div></div>
    </div>

    <h2>Covered Calls ({len(cc)} positions &middot; {_money(total_cc)})</h2>
    {cc_html}

    <h2>Cash-Secured Puts ({len(csp)} positions &middot; {_money(total_csp)})</h2>
    {csp_html}

    {longs_html}
    {flags_html}

  </div>
  <div class="ft">
    Live data from Interactive Brokers &middot; Prices via yfinance &middot; {datetime.now().strftime('%Y-%m-%d %H:%M')}
  </div>
</div>
</body></html>"""
    return html


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Daily Options Positions Email")
    parser.add_argument("--preview", action="store_true", help="Write HTML to /tmp, skip send")
    args = parser.parse_args()

    # Connect to IB
    from ib_insync import IB
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        log.info("Connected to IB")
    except Exception as e:
        log.error(f"IB connect failed: {e}")
        return

    try:
        acct = _fetch_account(ib)
        opts = _fetch_options(ib)
    finally:
        ib.disconnect()
        log.info("Disconnected from IB")

    if not opts:
        log.info("No options positions — nothing to email.")
        return

    symbols = list({o["symbol"] for o in opts})
    prices = _fetch_prices(symbols)
    enriched = _enrich(opts, prices)

    html = build_html(acct, enriched)
    today_str = date.today().strftime("%b %d, %Y")
    subject = f"Options Positions — {today_str}"

    if args.preview:
        preview_path = Path("/tmp/options_email_preview.html")
        preview_path.write_text(html)
        log.info(f"Preview written to {preview_path}")
        return

    # Also update the markdown report
    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # Recipients: primary (from config) + any extras
    EXTRA_RECIPIENTS = [
        "lrebbeck@vmrdevp.com",
    ]

    # Send via email_helper (Resend API)
    try:
        from email_helper import load_email_config, send_email, validate_email_config
        config = load_email_config()
        is_valid, err = validate_email_config(config)
        if not is_valid:
            log.error(f"Email config invalid: {err}")
            log.info("Falling back to Telegram summary")
            _send_telegram_fallback(enriched, acct)
            return

        all_recipients = [config.get("to_email", "")] + EXTRA_RECIPIENTS
        all_recipients = [r for r in all_recipients if r]

        for recipient in all_recipients:
            ok = send_email(subject, html, to_email=recipient, config=config)
            if ok:
                log.info(f"Email sent to {recipient}")
            else:
                log.warning(f"Email to {recipient} failed")

    except ImportError:
        log.error("email_helper not found — falling back to Telegram")
        _send_telegram_fallback(enriched, acct)


def _send_telegram_fallback(enriched: list[dict], acct: dict[str, float]) -> None:
    """Compact Telegram summary if email fails."""
    import os
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not (token and chat):
        log.warning("Telegram not configured either — no delivery channel available")
        return

    cc  = [r for r in enriched if r["type"] == "Covered Call"]
    csp = [r for r in enriched if r["type"] == "CSP"]
    total = sum(r["total_prem"] for r in cc + csp)
    nlv = acct.get("NetLiquidation", 0)
    flags = sum(1 for r in cc + csp if not r["compliant"])

    lines = [
        "<b>Options Daily Summary</b>",
        f"CC: {len(cc)} positions · ${sum(r['total_prem'] for r in cc):,.0f}",
        f"CSP: {len(csp)} positions · ${sum(r['total_prem'] for r in csp):,.0f}",
        f"Total premium: ${total:,.0f}",
        f"NLV: ${nlv:,.0f} · Flags: {flags}",
    ]

    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat, "text": "\n".join(lines), "parse_mode": "HTML"
    }).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=5)
        log.info("Telegram fallback sent")
    except Exception as e:
        log.error(f"Telegram fallback also failed: {e}")


if __name__ == "__main__":
    main()
