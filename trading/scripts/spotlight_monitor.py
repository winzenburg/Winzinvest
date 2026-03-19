#!/usr/bin/env python3
"""
Spotlight Monitor
==================
Watches high-conviction symbols from watchlist_spotlight.json every 30 min.
Sends Telegram + email alerts when breakout/volume/momentum conditions trigger.

Usage:
  python3 spotlight_monitor.py           # normal run
  python3 spotlight_monitor.py --once    # single check then exit
"""

import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

SCRIPTS_DIR    = Path(__file__).resolve().parent
TRADING_DIR    = SCRIPTS_DIR.parent
LOGS_DIR       = TRADING_DIR / "logs"
WATCHLIST      = TRADING_DIR / "watchlist_spotlight.json"
STATE_FILE     = LOGS_DIR / "spotlight_state.json"
EXEC_LOG_FILE  = LOGS_DIR / "spotlight_executions.json"

IB_HOST      = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT      = int(os.getenv("IB_PORT", "4001"))
IB_CLIENT_ID = 108

LOGS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

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
        logging.FileHandler(LOGS_DIR / "spotlight_monitor.log"),
    ],
)
log = logging.getLogger(__name__)

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")


# ── Data ──────────────────────────────────────────────────────────────────────

def _fetch(sym: str) -> dict[str, Any] | None:
    """Fetch OHLCV + derived stats for a symbol via yfinance."""
    try:
        import yfinance as yf
        h = yf.download(sym, period="30d", interval="1d", progress=False, auto_adjust=True)
        if h.empty:
            return None

        def _col(name: str):
            c = h[name]
            return c.iloc[:, 0] if hasattr(c, "columns") else c

        cl  = _col("Close")
        vol = _col("Volume")

        spot     = round(float(cl.iloc[-1]), 2)
        prev     = round(float(cl.iloc[-2]), 2)
        day_chg  = round((spot - prev) / prev * 100, 2)
        avg_vol  = float(vol.iloc[:-1].mean())
        today_vol= float(vol.iloc[-1])
        rvol     = round(today_vol / avg_vol, 2) if avg_vol > 0 else 0

        hi_10d   = round(float(cl.tail(10).max()), 2)
        lo_10d   = round(float(cl.tail(10).min()), 2)
        hi_20d   = round(float(cl.tail(20).max()), 2)

        # Simple RSI-14
        delta    = cl.diff()
        gain     = delta.clip(lower=0).rolling(14).mean()
        loss     = (-delta.clip(upper=0)).rolling(14).mean()
        rs       = gain / loss.replace(0, float("nan"))
        rsi_s    = (100 - 100 / (1 + rs))
        rsi      = round(float(rsi_s.iloc[-1]), 1) if not rsi_s.empty else 50.0

        # Consecutive up days
        up_days  = 0
        for i in range(1, min(6, len(cl))):
            if cl.iloc[-i] > cl.iloc[-(i + 1)]:
                up_days += 1
            else:
                break

        # Distance from 10d high
        pct_from_hi = round((spot - hi_10d) / hi_10d * 100, 1)

        return {
            "symbol": sym, "spot": spot, "prev": prev,
            "day_chg": day_chg, "rvol": rvol,
            "hi_10d": hi_10d, "lo_10d": lo_10d, "hi_20d": hi_20d,
            "rsi": rsi, "up_days": up_days,
            "pct_from_hi": pct_from_hi,
            "today_vol": int(today_vol), "avg_vol": int(avg_vol),
        }
    except Exception as e:
        log.warning(f"Could not fetch {sym}: {e}")
        return None


# ── Alert logic ───────────────────────────────────────────────────────────────

def _evaluate(data: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    """Return list of triggered alert strings for a symbol."""
    alerts: list[str] = []
    a = cfg.get("alerts", {})

    rvol_trig   = float(a.get("rvol_trigger", 2.0))
    gain_trig   = float(a.get("day_gain_trigger_pct", 5.0))
    breakout_px = float(a.get("breakout_price", 9999))
    rsi_reclaim = float(a.get("rsi_reclaim", 50))
    consec_days = int(a.get("consecutive_up_days", 2))

    if data["rvol"] >= rvol_trig:
        alerts.append(f"🔥 VOLUME SURGE: RVOL {data['rvol']:.1f}x (>{rvol_trig}x threshold)")

    if data["day_chg"] >= gain_trig:
        alerts.append(f"🚀 MOMENTUM: +{data['day_chg']:.1f}% today (>{gain_trig}% threshold)")

    if data["spot"] >= breakout_px and data["prev"] < breakout_px:
        alerts.append(f"📈 BREAKOUT: price crossed ${breakout_px:.0f} (was ${data['prev']:.2f})")

    if data["rsi"] >= rsi_reclaim and data.get("prev_rsi", 0) < rsi_reclaim:
        alerts.append(f"📊 RSI RECLAIM: RSI crossed {rsi_reclaim:.0f} (now {data['rsi']:.1f})")

    if data["up_days"] >= consec_days:
        alerts.append(f"📅 STREAK: {data['up_days']} consecutive up days")

    # Always-on context lines (informational, not alert)
    return alerts


# ── State management (de-dupe alerts per day) ─────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            s = json.loads(STATE_FILE.read_text())
            if s.get("date") == str(date.today()):
                return s
        except Exception:
            pass
    return {"date": str(date.today()), "alerted": {}}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _already_alerted(state: dict, sym: str, alert_key: str) -> bool:
    return alert_key in state["alerted"].get(sym, [])


def _mark_alerted(state: dict, sym: str, alert_key: str) -> None:
    state["alerted"].setdefault(sym, [])
    if alert_key not in state["alerted"][sym]:
        state["alerted"][sym].append(alert_key)


# ── Notifications ──────────────────────────────────────────────────────────────

def _telegram(msg: str) -> None:
    try:
        from notifications import send_telegram
        send_telegram(msg)
        return
    except ImportError:
        pass
    if not (TG_TOKEN and TG_CHAT):
        return
    url  = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}
    ).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=5)
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


def _email_alert(sym: str, alerts: list[str], data: dict) -> None:
    try:
        from email_helper import load_email_config, send_email, validate_email_config
        config = load_email_config()
        ok, _ = validate_email_config(config)
        if not ok:
            return

        chg_color = "#2e7d32" if data["day_chg"] >= 0 else "#c62828"
        sign      = "+" if data["day_chg"] >= 0 else ""
        alert_rows = "".join(f"<li style='margin:4px 0'>{a}</li>" for a in alerts)

        html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'></head>
<body style='font-family:-apple-system,sans-serif;background:#f0f2f5;padding:20px;margin:0'>
<div style='max-width:560px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.10)'>
  <div style='background:linear-gradient(135deg,#0f2027,#2c5364);color:#fff;padding:22px 28px'>
    <div style='font-size:11px;opacity:.65;text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px'>Spotlight Alert</div>
    <h1 style='margin:0;font-size:24px;font-weight:700'>{sym}</h1>
    <p style='margin:4px 0 0;opacity:.75;font-size:13px'>{datetime.now().strftime("%A, %B %d, %Y · %I:%M %p MT")}</p>
  </div>
  <div style='padding:24px 28px'>
    <div style='display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap'>
      <div style='flex:1;min-width:100px;background:#f8f9fb;border-radius:8px;padding:12px;text-align:center'>
        <div style='font-size:22px;font-weight:700'>${data["spot"]:,.2f}</div>
        <div style='font-size:10px;color:#6c757d;text-transform:uppercase;letter-spacing:.5px;margin-top:3px'>Price</div>
      </div>
      <div style='flex:1;min-width:100px;background:#f8f9fb;border-radius:8px;padding:12px;text-align:center'>
        <div style='font-size:22px;font-weight:700;color:{chg_color}'>{sign}{data["day_chg"]:.1f}%</div>
        <div style='font-size:10px;color:#6c757d;text-transform:uppercase;letter-spacing:.5px;margin-top:3px'>Today</div>
      </div>
      <div style='flex:1;min-width:100px;background:#f8f9fb;border-radius:8px;padding:12px;text-align:center'>
        <div style='font-size:22px;font-weight:700'>{data["rvol"]:.1f}x</div>
        <div style='font-size:10px;color:#6c757d;text-transform:uppercase;letter-spacing:.5px;margin-top:3px'>Rel. Volume</div>
      </div>
      <div style='flex:1;min-width:100px;background:#f8f9fb;border-radius:8px;padding:12px;text-align:center'>
        <div style='font-size:22px;font-weight:700'>{data["rsi"]:.0f}</div>
        <div style='font-size:10px;color:#6c757d;text-transform:uppercase;letter-spacing:.5px;margin-top:3px'>RSI 14</div>
      </div>
    </div>
    <div style='background:#fff8e1;border-left:4px solid #f59e0b;border-radius:6px;padding:14px 16px;margin-bottom:16px'>
      <div style='font-size:11px;font-weight:700;color:#92400e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px'>Triggered Signals</div>
      <ul style='margin:0;padding-left:18px;color:#78350f'>{alert_rows}</ul>
    </div>
    <table style='width:100%;font-size:13px;border-collapse:collapse'>
      <tr><td style='padding:5px 0;color:#6c757d'>10d Range</td>
          <td style='padding:5px 0;text-align:right'>${data["lo_10d"]:,.2f} – ${data["hi_10d"]:,.2f}</td></tr>
      <tr><td style='padding:5px 0;color:#6c757d'>% from 10d High</td>
          <td style='padding:5px 0;text-align:right'>{data["pct_from_hi"]:+.1f}%</td></tr>
      <tr><td style='padding:5px 0;color:#6c757d'>Consecutive Up Days</td>
          <td style='padding:5px 0;text-align:right'>{data["up_days"]}</td></tr>
      <tr><td style='padding:5px 0;color:#6c757d'>Today's Volume</td>
          <td style='padding:5px 0;text-align:right'>{data["today_vol"]:,}</td></tr>
    </table>
  </div>
  <div style='padding:14px 28px;background:#f8f9fb;color:#adb5bd;font-size:11px;text-align:center;border-top:1px solid #eaecef'>
    Winzinvest Spotlight Monitor · Auto-generated alert
  </div>
</div>
</body></html>"""

        subject = f"🔔 {sym} Alert — {', '.join(a.split(':')[0] for a in alerts[:2])}"
        send_email(subject, html, to_email=config.get("to_email", ""), config=config)
        log.info(f"Email alert sent for {sym}")
    except Exception as e:
        log.warning(f"Email alert failed for {sym}: {e}")


# ── Execution ─────────────────────────────────────────────────────────────────

def _get_nlv(ib: Any) -> float:
    for v in ib.accountValues():
        if v.tag == "NetLiquidation" and v.currency == "USD":
            return float(v.value)
    return 0.0


def _already_have_position(ib: Any, sym: str) -> bool:
    for p in ib.positions():
        if p.contract.symbol == sym and p.contract.secType == "STK" and p.position != 0:
            return True
    return False


def _load_exec_log() -> list[dict]:
    if EXEC_LOG_FILE.exists():
        try:
            return json.loads(EXEC_LOG_FILE.read_text())
        except Exception:
            pass
    return []


def _already_executed_today(sym: str) -> bool:
    today = str(date.today())
    for entry in _load_exec_log():
        if entry.get("symbol") == sym and entry.get("date") == today:
            return True
    return False


def _log_execution(record: dict) -> None:
    log_data = _load_exec_log()
    log_data.append(record)
    EXEC_LOG_FILE.write_text(json.dumps(log_data, indent=2))


def _entry_conditions_met(data: dict[str, Any], exec_cfg: dict) -> bool:
    cond      = exec_cfg.get("entry_conditions", {})
    require_all = cond.get("require_all", True)
    rvol_min  = float(cond.get("rvol_min", 0))
    gain_min  = float(cond.get("day_gain_min_pct", 0))

    rvol_ok   = data["rvol"]    >= rvol_min
    gain_ok   = data["day_chg"] >= gain_min

    if require_all:
        return rvol_ok and gain_ok
    return rvol_ok or gain_ok


def _execute_entry(sym: str, data: dict[str, Any], exec_cfg: dict) -> dict:
    """Place a market buy order sized at position_pct_nlv of NLV.
    Returns execution record dict.
    """
    from ib_insync import IB, Stock, MarketOrder, StopOrder
    try:
        from pre_trade_guard import PreTradeViolation, assert_no_flip
    except ImportError:
        PreTradeViolation = Exception  # type: ignore[assignment,misc]
        def assert_no_flip(*_a: Any, **_kw: Any) -> None:  # type: ignore[misc]
            pass

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
    except Exception as e:
        return {"symbol": sym, "status": "error", "error": f"IB connect failed: {e}",
                "date": str(date.today()), "timestamp": datetime.now().isoformat()}

    try:
        # Pre-trade guard — no position flips
        try:
            assert_no_flip(ib, sym, "LONG")
        except PreTradeViolation as e:
            return {"symbol": sym, "status": "blocked", "error": str(e),
                    "date": str(date.today()), "timestamp": datetime.now().isoformat()}

        # Skip if already holding
        if _already_have_position(ib, sym):
            return {"symbol": sym, "status": "skipped", "reason": "position already open",
                    "date": str(date.today()), "timestamp": datetime.now().isoformat()}

        # Size the order
        nlv       = _get_nlv(ib)
        pct_nlv   = float(exec_cfg.get("position_pct_nlv", 0.03))
        notional  = nlv * pct_nlv
        spot      = data["spot"]
        qty       = max(1, int(notional / spot))
        stop_pct  = float(exec_cfg.get("stop_loss_pct", 0.10))
        stop_px   = round(spot * (1 - stop_pct), 2)

        log.info(f"  EXECUTE {sym}: BUY {qty} shares @ ~${spot:.2f}  "
                 f"notional=${qty*spot:,.0f}  stop=${stop_px:.2f}")

        # Qualify stock contract
        contract = Stock(sym, "SMART", "USD")
        ib.qualifyContracts(contract)

        # Entry: market order (RTH only)
        entry_order       = MarketOrder("BUY", qty)
        entry_order.tif   = "DAY"
        entry_order.transmit = False   # wait until stop is also set

        entry_trade = ib.placeOrder(contract, entry_order)
        ib.sleep(0.5)

        # Attached stop-loss
        stop_order           = StopOrder("SELL", qty, stop_px)
        stop_order.tif       = "GTC"
        stop_order.parentId  = entry_trade.order.orderId
        stop_order.transmit  = True    # transmits both

        ib.placeOrder(contract, stop_order)
        ib.sleep(1)

        status = entry_trade.orderStatus.status
        filled = entry_trade.orderStatus.filled
        avg_px = entry_trade.orderStatus.avgFillPrice or spot

        record = {
            "symbol": sym, "side": "LONG", "qty": qty,
            "entry_price": avg_px, "stop_price": stop_px,
            "notional": round(qty * avg_px, 2),
            "order_id": entry_trade.order.orderId,
            "status": status, "filled": filled,
            "rvol_at_entry": data["rvol"],
            "day_chg_at_entry": data["day_chg"],
            "rsi_at_entry": data["rsi"],
            "date": str(date.today()),
            "timestamp": datetime.now().isoformat(),
            "thesis": exec_cfg.get("note", ""),
        }

        try:
            from trade_log_db import log_trade
            log_trade(
                symbol=sym,
                action="BUY",
                qty=qty,
                price=avg_px,
                strategy="spotlight_momentum",
                source_script="spotlight_monitor.py",
                stop_price=stop_px,
            )
            log.info("Logged spotlight trade to trades.db: BUY %s %d @ $%.4f", sym, qty, avg_px)
        except Exception as log_exc:
            log.warning("Could not log spotlight trade to trades.db (non-fatal): %s", log_exc)

        # Sell premium immediately after entry — but only on non-leveraged ETFs
        # or leveraged ETFs held > 5 days (wheel discipline)
        is_leveraged_etf = sym in ("GDXU", "KORU", "TQQQ", "SOXL", "LABU", "SPXL", "TNA")
        if qty >= 100 and not is_leveraged_etf:
            try:
                from post_entry_premium import write_covered_call
                cc = write_covered_call(ib, symbol=sym, shares_held=qty)
                log.info(
                    "Post-entry CC (%s): status=%s strike=%s premium=$%.0f  %s",
                    sym, cc["status"], cc.get("strike"), cc.get("premium_total", 0), cc.get("reason", ""),
                )
                record["covered_call"] = cc
            except Exception as cc_err:
                log.warning("Post-entry CC failed for %s: %s", sym, cc_err)

        return record

    finally:
        ib.disconnect()


# ── Main ──────────────────────────────────────────────────────────────────────

def run_check() -> None:
    if not WATCHLIST.exists():
        log.warning(f"Watchlist not found: {WATCHLIST}")
        return

    watch = json.loads(WATCHLIST.read_text())
    symbols = watch.get("symbols", [])
    if not symbols:
        return

    state = _load_state()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    any_alert = False

    for cfg in symbols:
        sym = cfg["symbol"]
        data = _fetch(sym)
        if data is None:
            log.warning(f"No data for {sym} — skipping")
            continue

        log.info(
            f"{sym}: ${data['spot']} ({data['day_chg']:+.1f}%) "
            f"RVOL={data['rvol']:.1f}x RSI={data['rsi']:.0f} "
            f"up_days={data['up_days']} pct_from_hi={data['pct_from_hi']:+.1f}%"
        )

        triggered = _evaluate(data, cfg)
        new_alerts = [
            a for a in triggered
            if not _already_alerted(state, sym, a.split(":")[0].strip())
        ]

        # ── Check entry execution ────────────────────────────────────────────
        exec_cfg  = cfg.get("execution", {})
        exec_enabled = exec_cfg.get("enabled", False)
        exec_record: dict | None = None

        if exec_enabled and _entry_conditions_met(data, exec_cfg):
            if _already_executed_today(sym):
                log.info(f"  → Entry conditions met for {sym} but already executed today — skipping")
            else:
                log.info(f"  → Entry conditions MET for {sym} — placing order")
                exec_record = _execute_entry(sym, data, exec_cfg)
                _log_execution(exec_record)
                log.info(f"  → Execution result: {exec_record.get('status')} "
                         f"qty={exec_record.get('qty')} fill={exec_record.get('entry_price')}")

        if new_alerts or exec_record:
            any_alert = True
            exec_lines: list[str] = []
            if exec_record:
                st = exec_record.get("status", "unknown")
                if st in ("Submitted", "PreSubmitted", "Filled"):
                    exec_lines = [
                        "",
                        f"✅ <b>ORDER PLACED:</b> BUY {exec_record.get('qty')} {sym} "
                        f"@ ~${exec_record.get('entry_price', 0):.2f} | "
                        f"Stop: ${exec_record.get('stop_price', 0):.2f} "
                        f"({int(exec_cfg.get('stop_loss_pct', 0.1)*100)}% below)",
                    ]
                else:
                    exec_lines = [f"", f"⚠️ Order status: {st} — {exec_record.get('error', '')}"]

            # Telegram
            tg_lines = (
                [
                    f"<b>🔔 {sym} Spotlight Alert</b>",
                    f"${data['spot']:,.2f}  {'+' if data['day_chg']>=0 else ''}{data['day_chg']:.1f}%  "
                    f"RVOL {data['rvol']:.1f}x  RSI {data['rsi']:.0f}",
                    "",
                ]
                + new_alerts
                + exec_lines
                + [
                    "",
                    f"10d range: ${data['lo_10d']:,.2f}–${data['hi_10d']:,.2f}  ({data['pct_from_hi']:+.1f}% from hi)",
                    f"<i>{now_str}</i>",
                ]
            )
            _telegram("\n".join(tg_lines))

            # Email
            all_msgs = new_alerts + ([f"ORDER: {exec_lines[1].replace('<b>','').replace('</b>','')}"] if exec_lines else [])
            _email_alert(sym, all_msgs, data)

            for a in new_alerts:
                _mark_alerted(state, sym, a.split(":")[0].strip())

            log.info(f"  → Alerts fired for {sym}: {new_alerts}")
        else:
            log.info(f"  → No new alerts for {sym}")

    _save_state(state)
    if not any_alert:
        log.info("Spotlight check complete — no new alerts")


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="Run once and exit")
    args = p.parse_args()
    log.info("=== SPOTLIGHT MONITOR ===")
    run_check()
    log.info("=== SPOTLIGHT MONITOR COMPLETE ===")


if __name__ == "__main__":
    main()
