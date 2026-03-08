#!/usr/bin/env node
/**
 * AMS NX Trade Engine v2 — Autonomous Monitor & Executor (FIXED)
 * 
 * V2 FIXES:
 * - Position state tracking (prevents duplicate entries)
 * - Entry/exit state machine
 * - Stop loss enforcement
 * - Take profit logic
 * - Proper risk checks per position
 * 
 * Run: node trading/nx-engine-monitor-v2.mjs
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');
const DASHBOARD_DATA = path.join(WORKSPACE, 'dashboard-data.json');
const TRADE_LOG = path.join(WORKSPACE, 'logs/trades.log');
const POSITIONS_LOG = path.join(WORKSPACE, 'logs/open-positions.json');

// ===================================================================
// POSITION STATE MANAGER
// ===================================================================

class PositionManager {
  constructor() {
    this.positions = this.loadPositions();
  }

  loadPositions() {
    try {
      if (fs.existsSync(POSITIONS_LOG)) {
        return JSON.parse(fs.readFileSync(POSITIONS_LOG, 'utf-8'));
      }
    } catch (e) {
      console.warn(`Failed to load positions:`, e.message);
    }
    return {};
  }

  savePositions() {
    fs.writeFileSync(POSITIONS_LOG, JSON.stringify(this.positions, null, 2));
  }

  openPosition(ticker, entryPrice, quantity, stopPrice, riskPerShare) {
    /**
     * PHASE 1: Open position with trailing stop framework
     * - No predetermined profit target (targetPrice removed)
     * - Track maxPrice for trailing stop
     * - Track partialExited flag for 2R partial logic
     */
    if (this.positions[ticker]) {
      return null; // Position already exists
    }

    const partialTarget = entryPrice + (riskPerShare * 2); // 2R target for 20-25% partial

    this.positions[ticker] = {
      ticker,
      entryPrice,
      quantity,
      quantityRemaining: quantity, // Track remaining shares after partial exit
      stopPrice,
      partialTarget, // 2R target for 20-25% partial exit only
      openedAt: new Date().toISOString(),
      status: 'OPEN',
      maxPrice: entryPrice, // For trailing stop calculation
      partialExited: false, // Flag: whether 20-25% has been taken at 2R
      trailStopPercent: 0.05, // 5% trailing stop (Covel chandelier equivalent)
    };

    this.savePositions();
    return this.positions[ticker];
  }

  partialExit(ticker, exitPrice, partialPct = 0.25) {
    /**
     * PHASE 1: Take partial exit (20-25%) at 2R, keep rest trailing
     */
    if (!this.positions[ticker]) {
      return null;
    }

    const pos = this.positions[ticker];
    const sharesToClose = Math.floor(pos.quantity * partialPct);
    const partialPnl = (exitPrice - pos.entryPrice) * sharesToClose;
    const partialPnlPct = ((exitPrice - pos.entryPrice) / pos.entryPrice) * 100;

    pos.partialExited = true;
    pos.quantityRemaining = pos.quantity - sharesToClose;
    pos.partialExitPrice = exitPrice;
    pos.partialExitAt = new Date().toISOString();
    pos.partialPnl = partialPnl;
    pos.partialPnlPct = partialPnlPct;
    // Status remains OPEN with trailing stop active on remaining position

    this.savePositions();

    return {
      ticker,
      sharesToClose,
      quantityRemaining: pos.quantityRemaining,
      partialExitPrice: exitPrice,
      partialPnl,
      partialPnlPct,
    };
  }

  closePosition(ticker, exitPrice, exitReason) {
    /**
     * Close a position (full exit)
     */
    if (!this.positions[ticker]) {
      return null; // No position to close
    }

    const pos = this.positions[ticker];
    const quantity = pos.quantityRemaining || pos.quantity;
    const pnl = (exitPrice - pos.entryPrice) * quantity;
    const pnlPct = ((exitPrice - pos.entryPrice) / pos.entryPrice) * 100;

    // Include partial exit P&L in final P&L if applicable
    const totalPnl = pnl + (pos.partialPnl || 0);
    const totalPnlPct = pos.partialExited 
      ? ((pos.partialPnl + pnl) / (pos.entryPrice * pos.quantity)) * 100
      : pnlPct;

    pos.exitPrice = exitPrice;
    pos.exitReason = exitReason;
    pos.closedAt = new Date().toISOString();
    pos.status = 'CLOSED';
    pos.pnl = totalPnl;
    pos.pnlPct = totalPnlPct;

    this.savePositions();
    
    return pos;
  }

  getPosition(ticker) {
    return this.positions[ticker];
  }

  getOpenPositions() {
    return Object.values(this.positions).filter(p => p.status === 'OPEN');
  }

  hasOpenPosition(ticker) {
    const pos = this.positions[ticker];
    return pos && pos.status === 'OPEN';
  }

  checkStopLoss(ticker, currentPrice) {
    /**
     * Check if stop loss is hit on full position
     */
    const pos = this.getPosition(ticker);
    if (!pos || pos.status !== 'OPEN') return null;

    if (currentPrice <= pos.stopPrice) {
      return { triggered: true, reason: 'STOP_LOSS', price: currentPrice };
    }

    return { triggered: false };
  }

  checkPartialExit(ticker, currentPrice) {
    /**
     * PHASE 1: Check if 2R partial exit target is hit
     * Exits 20-25% of position at 2R, then trails remaining 75-80%
     */
    const pos = this.getPosition(ticker);
    if (!pos || pos.status !== 'OPEN' || pos.partialExited) return null;

    if (currentPrice >= pos.partialTarget) {
      return { triggered: true, reason: 'PARTIAL_2R', price: currentPrice };
    }

    return { triggered: false };
  }

  checkTrailingStop(ticker, currentPrice) {
    /**
     * PHASE 1: Check if trailing stop is hit on remaining position
     * Trails stop at 5% below highest price since entry
     */
    const pos = this.getPosition(ticker);
    if (!pos || pos.status !== 'OPEN') return null;

    // Update max price
    if (currentPrice > pos.maxPrice) {
      pos.maxPrice = currentPrice;
    }

    // Calculate trailing stop
    const trailStop = pos.maxPrice * (1 - pos.trailStopPercent);

    if (currentPrice <= trailStop) {
      return { triggered: true, reason: 'TRAILING_STOP', price: currentPrice, trailStop };
    }

    return { triggered: false };
  }
}

// ===================================================================
// NX TRADE ENGINE v2 (Replicated Logic)
// ===================================================================

class NXTradeEngine {
  constructor(ticker, ohlcvData) {
    this.ticker = ticker;
    this.data = ohlcvData;
    this.n = ohlcvData.length;
  }

  epsilon(x) { return Math.max(x, 1e-9); }

  roc(source, len) {
    if (this.n < len) return 0;
    return ((source[this.n - 1] - source[this.n - 1 - len]) / this.epsilon(source[this.n - 1 - len])) * 100;
  }

  rsi(source, len) {
    if (this.n < len) return 50;
    const closes = source.slice(-len);
    let gains = 0, losses = 0;
    for (let i = 1; i < closes.length; i++) {
      const change = closes[i] - closes[i - 1];
      if (change > 0) gains += change;
      else losses -= change;
    }
    const avgGain = gains / len;
    const avgLoss = losses / len;
    const rs = avgGain / this.epsilon(avgLoss);
    return 100 - (100 / (1 + rs));
  }

  analyze() {
    const closes = this.data.map(d => d.close);
    const rocS = this.roc(closes, 21);
    const rocM = this.roc(closes, 63);
    const rocL = this.roc(closes, 126);
    const compMom = 0.2 * rocS + 0.3 * rocM + 0.5 * rocL;
    const rsi14 = this.rsi(closes, 14);
    const ema200 = closes.length >= 200 ? this.sma(closes, 200) : closes[this.n - 1];

    return {
      close: closes[this.n - 1],
      compMom,
      rsi14,
      bullish: closes[this.n - 1] > ema200,
      rocL,
    };
  }

  sma(source, len) {
    if (this.n < len) return source[this.n - 1];
    return source.slice(-len).reduce((a, b) => a + b, 0) / len;
  }

  getSignal() {
    const analysis = this.analyze();

    // Entry signal
    if (analysis.rsi14 > 50 && analysis.compMom > 0 && analysis.bullish) {
      return { type: 'LONG_ENTRY', analysis };
    }

    // Exit signal
    if (analysis.rsi14 < 50 || analysis.compMom < 0) {
      return { type: 'EXIT', analysis };
    }

    return { type: 'WAIT', analysis };
  }
}

// ===================================================================
// RISK MANAGER
// ===================================================================

class RiskManager {
  constructor(accountValue = 1000000, maxRiskPct = 0.02, peakEquity = 1000000) {
    this.accountValue = accountValue;
    this.peakEquity = peakEquity; // PHASE 2: Track peak equity for DD calculation
    this.maxRiskPct = maxRiskPct; // PHASE 1: Explicit per-trade risk percentage
    this.maxLossPerTrade = accountValue * maxRiskPct;
    this.maxConcurrentPositions = 2;
  }

  // PHASE 2 INSIGHT 3: Calculate current drawdown
  calculateDrawdown() {
    if (this.peakEquity <= 0) return 0;
    return (this.peakEquity - this.accountValue) / this.peakEquity;
  }

  // PHASE 2 INSIGHT 3: Get DD position size multiplier
  getDDMultiplier() {
    const dd = this.calculateDrawdown();
    
    // Circuit breaker: >20% DD = stop trading entirely
    if (dd > 0.20) return 0; // No new positions
    
    // Moderate DD: 5-15% → Keep position size steady (DO NOT reduce)
    // This is the Covel insight: recoveries happen at these levels
    if (dd > 0.05 && dd <= 0.15) return 1.0; // Full size
    
    // Small DD: <5% → Full position size
    if (dd <= 0.05) return 1.0; // Full size
    
    // Drawdown between 15-20%: Optional modest reduction (not required by Covel)
    if (dd > 0.15) return 0.75; // 75% size
    
    return 1.0; // Default: full size
  }

  canOpenPosition(openPositions, dd = 0) {
    const multiplier = this.getDDMultiplier();
    
    // If >20% DD, block all new positions
    if (multiplier === 0) return false;
    
    return openPositions.length < this.maxConcurrentPositions;
  }

  calculatePositionSize(entryPrice, stopPrice, dd = 0) {
    /**
     * PHASE 1 + 2 - Position sizing formula from Covel framework:
     * riskPerShare = entryPrice - initialStop
     * maxShares = (accountEquity * maxRiskPct * ddMultiplier) / riskPerShare
     * 
     * PHASE 2 INSIGHT 3: Apply DD multiplier to position size
     * - >20% DD: Block all entries (multiplier = 0)
     * - 15-20% DD: Optional 75% size reduction
     * - 5-15% DD: FULL SIZE (key Covel insight: recoveries happen here)
     * - <5% DD: Full size
     */
    const riskPerShare = Math.abs(entryPrice - stopPrice);
    if (riskPerShare <= 0) return { shares: 0, risk: 0, display: 'N/A', ddMultiplier: 1 };

    const ddMultiplier = this.getDDMultiplier();
    const adjustedRisk = this.maxLossPerTrade * ddMultiplier;
    const maxShares = Math.floor(adjustedRisk / riskPerShare);
    
    let displayStr = `${maxShares} shares @ ${this.maxRiskPct * 100}% risk`;
    if (ddMultiplier < 1.0) {
      const currentDD = (this.calculateDrawdown() * 100).toFixed(1);
      displayStr += ` (DD: ${currentDD}%, size: ${(ddMultiplier * 100).toFixed(0)}%)`;
    }
    if (ddMultiplier === 0) {
      displayStr = `BLOCKED - Drawdown >20%`;
    }
    
    return { 
      shares: Math.max(maxShares, 1), 
      risk: riskPerShare,
      display: displayStr,
      ddMultiplier,
    };
  }
}

// ===================================================================
// MAIN MONITOR LOOP
// ===================================================================

async function fetchLiveData(ticker) {
  try {
    const pythonCmd = `python3 << 'EOF'
import yfinance as yf
import json
ticker = "${ticker}"
data = yf.download(ticker, period="1y", progress=False)
if data.empty:
    print(json.dumps({"error": "No data"}))
else:
    ohlcv = []
    for date, row in data.iterrows():
        ohlcv.append({
            "time": date.strftime("%Y-%m-%d"),
            "open": float(row['Open']),
            "high": float(row['High']),
            "low": float(row['Low']),
            "close": float(row['Close']),
            "volume": int(row['Volume'])
        })
    print(json.dumps(ohlcv))
EOF`;

    const output = execSync(pythonCmd, { encoding: 'utf-8', timeout: 30000 });
    const data = JSON.parse(output);
    if (data.error) return null;
    return data;
  } catch (e) {
    return null;
  }
}

async function monitorCandidates() {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`AMS NX TRADE ENGINE v2 — FIXED MONITOR RUN`);
  console.log(`Time: ${new Date().toLocaleTimeString()}`);
  console.log(`${'='.repeat(60)}\n`);

  // Load screener results
  let dashboardData = {};
  if (fs.existsSync(DASHBOARD_DATA)) {
    dashboardData = JSON.parse(fs.readFileSync(DASHBOARD_DATA, 'utf-8'));
  }

  const candidates = [
    ...(dashboardData.screener?.tier3 || []),
    ...(dashboardData.screener?.tier2 || []),
  ].slice(0, 20);

  if (!candidates || candidates.length === 0) {
    console.log('No candidates in dashboard.\n');
    return;
  }

  // Initialize managers
  const positionMgr = new PositionManager();
  const riskMgr = new RiskManager(1000000, 0.02); // PHASE 1: 2% per-trade risk

  console.log(`Monitoring ${candidates.length} candidates...`);
  console.log(`Open positions: ${positionMgr.getOpenPositions().length}`);
  console.log(`Max risk per trade: ${(riskMgr.maxRiskPct * 100).toFixed(1)}%\n`);

  // Scan each candidate
  let entries = 0, exits = 0, partials = 0;

  for (const candidate of candidates) {
    const ticker = candidate.symbol;
    const ohlcv = await fetchLiveData(ticker);
    
    if (!ohlcv || ohlcv.length < 126) continue;

    const currentPrice = ohlcv[ohlcv.length - 1].close;
    const engine = new NXTradeEngine(ticker, ohlcv);
    const signal = engine.getSignal();

    // CHECK EXITS FIRST
    if (positionMgr.hasOpenPosition(ticker)) {
      const pos = positionMgr.getPosition(ticker);

      // Check stop loss (full exit)
      const stopCheck = positionMgr.checkStopLoss(ticker, currentPrice);
      if (stopCheck.triggered) {
        const closed = positionMgr.closePosition(ticker, currentPrice, 'STOP_LOSS_HIT');
        console.log(`  🛑 ${ticker}: CLOSED (Stop Loss) | Total PnL: ${closed.pnlPct.toFixed(2)}%`);
        exits++;
        continue;
      }

      // PHASE 1: Check for partial exit at 2R (if not already taken)
      if (!pos.partialExited) {
        const partialCheck = positionMgr.checkPartialExit(ticker, currentPrice);
        if (partialCheck.triggered) {
          const partial = positionMgr.partialExit(ticker, currentPrice, 0.25);
          console.log(`  💰 ${ticker}: PARTIAL EXIT (2R) | Sold: ${partial.sharesToClose} shares @ ${partial.partialExitPrice.toFixed(2)} | Remaining: ${partial.quantityRemaining} shares | Partial PnL: ${partial.partialPnlPct.toFixed(2)}%`);
          partials++;
          // Position stays open, trailing stop active on remaining
        }
      }

      // PHASE 1: Check trailing stop on remaining position
      const trailCheck = positionMgr.checkTrailingStop(ticker, currentPrice);
      if (trailCheck.triggered) {
        const closed = positionMgr.closePosition(ticker, currentPrice, 'TRAILING_STOP');
        const finalPnl = pos.partialExited ? closed.pnlPct : closed.pnlPct;
        console.log(`  📉 ${ticker}: CLOSED (Trailing Stop) | Trail Level: ${trailCheck.trailStop.toFixed(2)} | Total PnL: ${finalPnl.toFixed(2)}%`);
        exits++;
        continue;
      }

      // Check exit signal
      if (signal.type === 'EXIT') {
        const closed = positionMgr.closePosition(ticker, currentPrice, 'SIGNAL_EXIT');
        console.log(`  🔴 ${ticker}: CLOSED (Exit Signal) | Total PnL: ${closed.pnlPct.toFixed(2)}%`);
        exits++;
        continue;
      }

      // Position still open, skip entry check
      continue;
    }

    // CHECK ENTRIES (only if no open position)
    if (signal.type === 'LONG_ENTRY') {
      // Refresh open positions count
      const currentOpenPositions = positionMgr.getOpenPositions();
      
      // Can we open?
      if (!riskMgr.canOpenPosition(currentOpenPositions)) {
        console.log(`  ⏸️  ${ticker}: Signal detected but max positions reached (${currentOpenPositions.length}/${riskMgr.maxConcurrentPositions})`);
        continue;
      }

      // PHASE 1: Calculate position size per Covel framework
      const stopPrice = currentPrice * 0.95; // 5% stop
      const riskPerShare = currentPrice - stopPrice;
      const sizing = riskMgr.calculatePositionSize(currentPrice, stopPrice);
      const quantity = sizing.shares;

      // Open position with trailing stop (no TP1/TP2)
      const pos = positionMgr.openPosition(ticker, currentPrice, quantity, stopPrice, riskPerShare);
      if (pos) {
        console.log(`  🎯 ${ticker}: OPENED | ${quantity} shares @ ${currentPrice.toFixed(2)}`);
        console.log(`     ├─ Stop: ${stopPrice.toFixed(2)} | Risk per share: $${riskPerShare.toFixed(2)}`);
        console.log(`     ├─ Partial target (2R): ${pos.partialTarget.toFixed(2)} (sell 25% here)`);
        console.log(`     └─ Trail: 5% below high-water mark (no predetermined profit target)`);
        console.log(`     [MAX SHARES @ 2% RISK: ${sizing.display}]`);
        entries++;
      }
    }
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log(`Entries: ${entries} | Partials: ${partials} | Exits: ${exits} | Open: ${positionMgr.getOpenPositions().length}`);
  console.log(`${'='.repeat(60)}\n`);
}

// ===================================================================
// ENTRY POINT
// ===================================================================

async function main() {
  try {
    await monitorCandidates();
  } catch (e) {
    console.error('\n❌ Monitor failed:', e.message);
    process.exit(1);
  }
}

main();
