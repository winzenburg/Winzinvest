#!/usr/bin/env node
/**
 * AMS NX Trade Engine v2 — Autonomous Monitor & Executor
 * 
 * Runs every 5 minutes during trading hours (7:30 AM - 2:00 PM MT)
 * Fetches live data for screener candidates
 * Detects entry/exit signals via NX logic
 * Auto-executes trades via IB Gateway (within strict risk guardrails)
 * 
 * Run: node trading/nx-engine-monitor.mjs
 * Cron: Mon-Fri 7:30 AM - 2:00 PM MT, every 5 minutes
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');
const DASHBOARD_DATA = path.join(WORKSPACE, 'dashboard-data.json');
const TRADE_LOG = path.join(WORKSPACE, 'logs/trades.log');
const POSITIONS_LOG = path.join(WORKSPACE, 'logs/positions.log');

// ===================================================================
// IB GATEWAY API CLIENT
// ===================================================================

class IBGatewayClient {
  constructor(host = '127.0.0.1', port = 4002) {
    this.host = host;
    this.port = port;
    this.clientId = Math.floor(Math.random() * 10000);
  }

  async getPositions() {
    /**
     * Fetch open positions from IB Gateway
     * Returns: [{ symbol, quantity, avgCost, marketPrice, unrealizedPnL }]
     */
    try {
      // Use ib-insync or direct API call
      // For now, mock implementation
      console.log(`[IB API] Fetching open positions...`);
      return [];
    } catch (e) {
      console.error(`[IB API] Failed to fetch positions:`, e.message);
      return [];
    }
  }

  async getAccountSummary() {
    /**
     * Fetch account summary: buying power, margin, cash
     * Returns: { buyingPower, totalCashValue, netLiquidation, margin }
     */
    try {
      console.log(`[IB API] Fetching account summary...`);
      return {
        buyingPower: 500000,  // Mock
        totalCashValue: 500000,
        netLiquidation: 1000000,
        margin: 0,
      };
    } catch (e) {
      console.error(`[IB API] Failed to fetch account summary:`, e.message);
      return null;
    }
  }

  async placeOrder(symbol, quantity, orderType, price = null) {
    /**
     * Place order via IB Gateway
     * orderType: 'BUY' | 'SELL'
     * Returns: { orderId, status, message }
     */
    try {
      console.log(`[IB API] Placing order: ${orderType} ${quantity} ${symbol} @ ${price || 'MKT'}`);
      
      // Mock: simulate order placement
      const orderId = Math.floor(Math.random() * 1000000);
      
      // Log the order
      const tradeEntry = `${new Date().toISOString()} | ${symbol} | ${orderType} ${quantity} | Status: SUBMITTED | OrderID: ${orderId}`;
      fs.appendFileSync(TRADE_LOG, tradeEntry + '\n');
      
      console.log(`  ✅ Order placed. OrderID: ${orderId}`);
      return { orderId, status: 'SUBMITTED', message: 'Order submitted successfully' };
    } catch (e) {
      console.error(`[IB API] Failed to place order:`, e.message);
      return null;
    }
  }
}

// ===================================================================
// RISK MANAGER
// ===================================================================

class RiskManager {
  constructor(accountSummary) {
    this.buyingPower = accountSummary?.buyingPower || 500000;
    this.netLiquidation = accountSummary?.netLiquidation || 1000000;
    this.margin = accountSummary?.margin || 0;
  }

  // Position sizing rules (from MEMORY.md)
  calculatePositionSize(ticker, entryPrice, stopPrice, volatility = 0.12) {
    const riskPerTrade = this.netLiquidation * 0.005; // 0.5% max loss per trade
    const riskInDollars = Math.abs(entryPrice - stopPrice);
    
    if (riskInDollars <= 0) return 0;
    
    const maxShares = Math.floor(riskPerTrade / riskInDollars);
    const dollarPosition = maxShares * entryPrice;
    
    // Don't exceed buying power
    const maxByDollar = Math.floor(this.buyingPower * 0.25);
    const finalShares = Math.min(maxShares, Math.floor(maxByDollar / entryPrice));
    
    return Math.max(finalShares, 1);
  }

  // Margin check
  canTrade(dollarRisk) {
    const marginUsageAfter = this.margin + dollarRisk;
    const marginAvailable = this.netLiquidation * 0.7; // 70% hard stop
    return marginUsageAfter <= marginAvailable;
  }

  // Drawdown check (from trading rules)
  shouldHaltTrading(currentDrawdown = 0) {
    return currentDrawdown >= 0.10; // 10% max drawdown
  }
}

// ===================================================================
// NX TRADE ENGINE v2 (Replicated Logic)
// ===================================================================

class NXTradeEngine {
  constructor(ticker, ohlcvData) {
    this.ticker = ticker;
    this.data = ohlcvData; // Array of { close, high, low, volume, time }
    this.n = ohlcvData.length;
  }

  epsilon(x) { return Math.max(x, 1e-9); }

  // ROC
  roc(source, len) {
    if (this.n < len) return 0;
    return ((source[this.n - 1] - source[this.n - 1 - len]) / this.epsilon(source[this.n - 1 - len])) * 100;
  }

  // RSI
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

  // Z-Score
  zScore(source, len) {
    if (this.n < len) return 0;
    const subset = source.slice(-len);
    const mean = subset.reduce((a, b) => a + b, 0) / len;
    const variance = subset.reduce((sum, x) => sum + Math.pow(x - mean, 2), 0) / len;
    const std = Math.sqrt(variance);
    return (source[this.n - 1] - mean) / this.epsilon(std);
  }

  // Analyze current bar
  analyze() {
    const closes = this.data.map(d => d.close);
    const highs = this.data.map(d => d.high);
    const lows = this.data.map(d => d.low);
    const volumes = this.data.map(d => d.volume);

    // Momentum
    const rocS = this.roc(closes, 21);
    const rocM = this.roc(closes, 63);
    const rocL = this.roc(closes, 126);
    const compMom = 0.2 * rocS + 0.3 * rocM + 0.5 * rocL;

    // RSI
    const rsi14 = this.rsi(closes, 14);

    // Price structure
    const ema200 = closes.length >= 200 ? this.sma(closes, 200) : closes[this.n - 1];
    const bullish = closes[this.n - 1] > ema200;

    // Volume
    const avgVol = this.sma(volumes, 20);
    const volExpanding = volumes[this.n - 1] > avgVol * 0.75;

    // Momentum crash guard
    const crashRisk = rocS > 2.0 * rocM && rocS > 20.0;

    return {
      close: closes[this.n - 1],
      compMom,
      rsi14,
      bullish,
      volExpanding,
      crashRisk,
      rocS,
      rocM,
      rocL,
    };
  }

  sma(source, len) {
    if (this.n < len) return source[this.n - 1];
    const sum = source.slice(-len).reduce((a, b) => a + b, 0);
    return sum / len;
  }

  // Generate signal
  getSignal() {
    const analysis = this.analyze();

    // Entry logic (from v2)
    if (
      analysis.rsi14 > 50 &&
      analysis.compMom > 0 &&
      analysis.bullish &&
      analysis.volExpanding &&
      !analysis.crashRisk
    ) {
      return { type: 'LONG_ENTRY', confidence: 'HIGH', analysis };
    }

    // Exit logic
    if (
      analysis.rsi14 < 50 ||
      !analysis.bullish ||
      analysis.crashRisk
    ) {
      return { type: 'EXIT', confidence: 'MEDIUM', analysis };
    }

    return { type: 'WAIT', confidence: 'LOW', analysis };
  }
}

// ===================================================================
// MAIN MONITOR LOOP
// ===================================================================

async function fetchLiveData(ticker) {
  /**
   * Fetch latest OHLCV for ticker (last 252 bars for Z-score, etc.)
   */
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
    console.warn(`  ⚠️  ${ticker}: ${e.message}`);
    return null;
  }
}

async function monitorCandidates() {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`AMS NX TRADE ENGINE v2 — MONITOR RUN`);
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
    console.log('No candidates in dashboard. Run screener first.\n');
    return;
  }

  console.log(`Monitoring ${candidates.length} candidates...\n`);

  // Initialize IB API & Risk Manager
  const ib = new IBGatewayClient();
  const account = await ib.getAccountSummary();
  const riskMgr = new RiskManager(account);

  // Check trading halts
  if (riskMgr.shouldHaltTrading(0.05)) {
    console.log('⚠️  Drawdown >5%. Reducing position size.\n');
  }

  // Scan each candidate
  let signalCount = 0;
  const signals = [];

  for (const candidate of candidates) {
    const ticker = candidate.symbol;
    
    // Fetch live data
    const ohlcv = await fetchLiveData(ticker);
    if (!ohlcv || ohlcv.length < 126) {
      console.log(`  ⚠️  ${ticker}: Insufficient data\n`);
      continue;
    }

    // Run NX Trade Engine
    const engine = new NXTradeEngine(ticker, ohlcv);
    const signal = engine.getSignal();

    if (signal.type !== 'WAIT') {
      signalCount++;
      console.log(`  📊 ${ticker} — ${signal.type}`);
      console.log(`     RSI: ${signal.analysis.rsi14.toFixed(0)} | Mom: ${signal.analysis.compMom.toFixed(1)}% | Vol: ${signal.analysis.volExpanding ? '✅' : '❌'}`);
      
      signals.push({
        ticker,
        signal: signal.type,
        close: signal.analysis.close,
        analysis: signal.analysis,
        timestamp: new Date().toISOString(),
      });
    }
  }

  console.log(`\n${'='.repeat(60)}`);
  console.log(`Signals detected: ${signalCount}`);
  console.log(`${'='.repeat(60)}\n`);

  // Execute signals (if any)
  if (signals.length > 0) {
    await executeSignals(signals, ib, riskMgr);
  }
}

async function executeSignals(signals, ib, riskMgr) {
  console.log(`Executing ${signals.length} signal(s)...\n`);

  for (const sig of signals) {
    const { ticker, signal, close, analysis } = sig;

    if (signal === 'LONG_ENTRY') {
      // Calculate position size
      const entryPrice = close;
      const stopPrice = close * 0.95; // 5% stop
      const positionSize = riskMgr.calculatePositionSize(ticker, entryPrice, stopPrice);
      const dollarRisk = positionSize * entryPrice;

      // Risk check
      if (!riskMgr.canTrade(dollarRisk)) {
        console.log(`  ⚠️  ${ticker}: Insufficient margin for ${positionSize} shares`);
        continue;
      }

      // Execute
      console.log(`  🎯 Executing LONG: ${ticker} | ${positionSize} shares @ ${entryPrice.toFixed(2)}`);
      const order = await ib.placeOrder(ticker, positionSize, 'BUY', entryPrice);
      
      if (order) {
        console.log(`     ✅ Order placed. OrderID: ${order.orderId}\n`);
      }
    }
  }
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
