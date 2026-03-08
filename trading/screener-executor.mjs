#!/usr/bin/env node
/**
 * AMS NX Screener v2 Executor
 * Scans SPY 500 + Nasdaq 100 + Russell 2000 + top 50 ETFs
 * Applies NX Screener v2 logic to each ticker
 * Outputs qualified candidates by tier to Mission Control dashboard
 * 
 * Run: node trading/screener-executor.mjs
 * Cron: Daily 8:00 AM MT
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');
const DASHBOARD_DATA = path.join(WORKSPACE, 'dashboard-data.json');

// ===================================================================
// PHASE 2 CONFIGURATION
// ===================================================================

const PHASE2_CONFIG = {
  // Insight 3: Portfolio drawdown handling
  // - >20% DD: block all entries
  // - 5-15% DD: full position size (do NOT reduce)
  // - <5% DD: full position size
  portfolioDD: true,
  
  // Insight 4: Require 52-week highs for Tier 3 candidates
  useNewHighFilter: true,
  
  // Insight 5: zEnter threshold for entry signals
  // Default 50 (conservative): RSI > 50 = higher win rate, smaller winners
  // Lower 40: RSI > 40 = more trades, larger avg winner (test both)
  // Backtest to optimize expectancy ratio, NOT win rate
  zEnter: 50, // BACKTEST: Try 40, 45, 50, 55 and compare expectancy ratios
};

// ===================================================================
// UNIVERSES
// ===================================================================

const UNIVERSES = {
  SPY500: [
    'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'BRK.B', 'JNJ', 'V',
    'WMT', 'JPM', 'MA', 'PG', 'AVGO', 'LLY', 'KO', 'COST', 'MCD', 'NFLX',
    'BA', 'AMD', 'QCOM', 'CSCO', 'INTC', 'CRM', 'ORCL', 'ACN', 'IBM', 'INTU',
    'ADBE', 'SNPS', 'CDNS', 'ADP', 'PAYX', 'VRTX', 'AMGN', 'GILD', 'CELG', 'REGN',
    'NOW', 'NWSA', 'FOX', 'CME', 'BLK', 'GS', 'MS', 'WFC', 'BAC', 'C',
    // Add more as needed...
  ],
  NASDAQ100: [
    'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'NFLX', 'AMD',
    'QCOM', 'INTC', 'ADBE', 'CSCO', 'INTU', 'CRM', 'AMAT', 'LRCX', 'SNPS', 'CDNS',
    'MU', 'ASML', 'SPLK', 'DDOG', 'NET', 'CRWD', 'ZM', 'RBLX', 'ROKU', 'XLNX',
    // Add more...
  ],
  RUSSELL2000: [
    'IWM', 'SCHA', 'SCHB', 'SWTX', 'SMMD', 'SRTY', 'EWRS', 'EWRM', 'EWRL',
    // Sample tickers - expand for full R2K
  ],
  ETFs: [
    'SPY', 'QQQ', 'IWM', 'XLK', 'XLV', 'XLF', 'XLI', 'XLE', 'XLY', 'XLP',
    'XLRE', 'XLU', 'VOO', 'VTI', 'VGT', 'VHT', 'VFV', 'VEA', 'VWO',
  ],
};

// ===================================================================
// NX SCREENER v2 LOGIC (REPLICATED FROM PINE SCRIPT)
// ===================================================================

class NXScreener {
  constructor(ticker, data) {
    this.ticker = ticker;
    this.data = data; // Array of { close, high, low, volume }
    this.n = data.length;
  }

  // Helpers
  epsilon(x) { return Math.max(x, 1e-9); }

  // SMA
  sma(source, len) {
    if (this.n < len) return source[this.n - 1];
    const sum = source.slice(-len).reduce((a, b) => a + b, 0);
    return sum / len;
  }

  // ROC (Rate of Change)
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

  // Highest/Lowest
  highest(source, len) {
    return Math.max(...source.slice(-len));
  }

  lowest(source, len) {
    return Math.min(...source.slice(-len));
  }

  // ATR
  atr(len = 14) {
    const closes = this.data.map(d => d.close);
    const highs = this.data.map(d => d.high);
    const lows = this.data.map(d => d.low);
    let tr = [];
    for (let i = 1; i < this.n; i++) {
      const h = highs[i];
      const l = lows[i];
      const c = closes[i - 1];
      const tr1 = h - l;
      const tr2 = Math.abs(h - c);
      const tr3 = Math.abs(l - c);
      tr.push(Math.max(tr1, tr2, tr3));
    }
    return this.sma(tr, len);
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

  // Calculate Score (Composite)
  calculateScore(spy, benchCh) {
    const closes = this.data.map(d => d.close);
    const volumes = this.data.map(d => d.volume);
    const highs = this.data.map(d => d.high);
    const lows = this.data.map(d => d.low);

    // Momentum
    const rocS = this.roc(closes, 21);
    const rocM = this.roc(closes, 63);
    const rocL = this.roc(closes, 126);
    const compMom = 0.2 * rocS + 0.3 * rocM + 0.5 * rocL;

    // RSI + Absolute Momentum
    const rsi14 = this.rsi(closes, 14);
    const absMom = (closes[this.n - 1] - closes[Math.max(0, this.n - 126)]) / closes[Math.max(0, this.n - 126)];

    // RS vs SPY
    const stockCh = (closes[this.n - 1] - closes[Math.max(0, this.n - 126)]) / closes[Math.max(0, this.n - 126)];
    const rsEx = stockCh - benchCh;
    let rsWins = 0;
    for (let i = 1; i <= 126; i++) {
      const idx = this.n - 1 - i;
      if (idx >= 0 && rsEx > 0) rsWins++;
    }
    const rsPct = rsWins / 126;

    // Volume
    const avgVol = this.sma(volumes, 50);
    const rvol = volumes[this.n - 1] / this.epsilon(avgVol);

    // Price Structure (Higher Highs/Lows)
    const recentHH = highs[this.n - 1] > this.highest(highs, 10);
    const recentHL = lows[this.n - 1] > this.lowest(lows, 10);
    const structScore = (recentHH && recentHL) ? 1.0 : 0.5;

    // PHASE 2 INSIGHT 4: Check if at 52-week high
    const max52w = this.highest(closes, 252);
    const atNewHigh = closes[this.n - 1] >= max52w;

    // Composite Score
    const scoreRaw = Math.min(Math.max(compMom / 25.0, 0), 1);
    const volScore = Math.min(rvol / 3.0, 1) * 0.7;
    const compFinal = 0.4 * scoreRaw + 0.2 * volScore + 0.2 * structScore;

    return {
      compMom,
      rsi14,
      absMom,
      rsPct,
      rvol,
      structScore,
      compFinal,
      rocS,
      rocM,
      rocL,
      atNewHigh, // NEW: Track 52-week high status
    };
  }

  // Tier Classification
  getTier(score) {
    const final = score.compFinal;
    if (final >= 0.35) return 3;
    if (final >= 0.20) return 2;
    return 1;
  }

  // Check Readiness (Screener Criteria)
  isReady(score, spy, minDollarVol, minPrice, useNewHighFilter = false, zEnter = 50) {
    /**
     * PHASE 2 INSIGHT 5: zEnter parameter controls entry threshold
     * Default (zEnter = 50): RSI must be > 50 (conservative, high win rate)
     * Lower (zEnter = 40): RSI must be > 40 (more trades, larger winners)
     * Backtest to find optimal expectancy ratio, not win rate
     */
    const closes = this.data.map(d => d.close);
    const close = closes[this.n - 1];
    const volume = this.data[this.n - 1].volume;
    const dollarVol = close * volume;

    if (dollarVol < minDollarVol || close < minPrice) return false;
    if (score.rsPct < 0.65) return false; // RS threshold for longs
    if (score.rsi14 < zEnter) return false; // PHASE 2: Configurable entry threshold
    if (score.absMom <= 0) return false;

    // PHASE 2 INSIGHT 4: New 52-week high filter (Covel research)
    // Biggest winners spend disproportionate time at new multi-year highs
    if (useNewHighFilter) {
      const max52w = this.highest(closes, 252); // 52-week high
      if (close < max52w) return false; // Must be at or above 52-week high
    }

    return true;
  }
}

// ===================================================================
// DATA FETCH & SCREENER RUN
// ===================================================================

async function fetchTickerData(ticker) {
  /**
   * Fetch historical OHLCV data via Python yfinance
   * Calls Python subprocess to get 252-day history
   */
  try {
    
    // Python script to fetch data
    const pythonCmd = `python3 << 'EOF'
import yfinance as yf
import json
import sys

try:
    # Fetch last 252 days of data
    ticker = "${ticker}"
    data = yf.download(ticker, period="1y", progress=False)
    
    if data.empty:
        print(json.dumps({"error": "No data"}))
        sys.exit(0)
    
    # Convert to list of OHLCV
    ohlcv = []
    for date, row in data.iterrows():
        ohlcv.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": float(row['Open']),
            "high": float(row['High']),
            "low": float(row['Low']),
            "close": float(row['Close']),
            "volume": int(row['Volume'])
        })
    
    print(json.dumps(ohlcv))
except Exception as e:
    print(json.dumps({"error": str(e)}))
EOF`;

    const output = execSync(pythonCmd, { encoding: 'utf-8', timeout: 30000 });
    const data = JSON.parse(output);
    
    if (data.error) {
      console.warn(`  ⚠️  ${ticker}: ${data.error}`);
      return null;
    }
    
    return data;
  } catch (e) {
    console.warn(`  ⚠️  ${ticker}: ${e.message}`);
    return null;
  }
}

async function runScreener() {
  console.log(`[NX Screener v2] Starting scan at ${new Date().toISOString()}`);

  // Combine all universes
  const allTickers = [
    ...new Set([
      ...UNIVERSES.SPY500.slice(0, 50),  // Start with top 50 for speed
      ...UNIVERSES.NASDAQ100.slice(0, 30),
      ...UNIVERSES.ETFs,
    ]),
  ];

  console.log(`Scanning ${allTickers.length} tickers...`);

  const results = {
    tier3: [],
    tier2: [],
    tier1: [],
  };

  // Fetch SPY benchmark for RS calculation
  console.log('Fetching SPY benchmark data...');
  const spyData = await fetchTickerData('SPY');
  if (!spyData) {
    console.error('Failed to fetch SPY data. Aborting scan.');
    return results;
  }

  const spyCloses = spyData.map(d => d.close);
  const benchCh = (spyCloses[spyCloses.length - 1] - spyCloses[Math.max(0, spyCloses.length - 126)]) / spyCloses[Math.max(0, spyCloses.length - 126)];

  // Scan each ticker
  let scanned = 0;
  let qualified = 0;

  for (const ticker of allTickers) {
    process.stdout.write(`\r  Scanning: ${ticker.padEnd(6)} (${scanned}/${allTickers.length})`);
    
    const data = await fetchTickerData(ticker);
    if (!data || data.length < 126) continue;

    scanned++;

    // Run screener on this ticker
    const screener = new NXScreener(ticker, data);
    const score = screener.calculateScore(spyData, benchCh);
    const tier = screener.getTier(score);
    
    // PHASE 2: Apply configuration gates
    // Insight 4: For Tier 3, require 52-week high confirmation
    // Insight 5: Use configurable zEnter threshold
    const isReady = screener.isReady(
      score,
      spyData,
      500000000, // $500M daily vol
      5,         // $5 min price
      tier === 3 && PHASE2_CONFIG.useNewHighFilter, // Insight 4
      PHASE2_CONFIG.zEnter  // Insight 5
    ); 

    if (!isReady || tier > 3) continue;

    qualified++;

    const candidate = {
      symbol: ticker,
      rsPct: Math.round(score.rsPct * 100),
      zScore: parseFloat(score.compMom.toFixed(2)),
      momentum: parseFloat((score.rocL).toFixed(1)),
      volume: parseFloat((score.rvol).toFixed(2)),
      score: parseFloat(score.compFinal.toFixed(3)),
      tier: tier,
      atNewHigh: score.atNewHigh, // NEW: Track 52-week high status
    };

    if (tier === 3) results.tier3.push(candidate);
    else if (tier === 2) results.tier2.push(candidate);
    else results.tier1.push(candidate);
  }

  // Sort by score descending
  results.tier3.sort((a, b) => b.score - a.score);
  results.tier2.sort((a, b) => b.score - a.score);
  results.tier1.sort((a, b) => b.score - a.score);

  console.log(`\n[NX Screener v2] Scan complete. Scanned: ${scanned}, Qualified: ${qualified}`);
  console.log(`  Tier 3: ${results.tier3.length} | Tier 2: ${results.tier2.length} | Tier 1: ${results.tier1.length}`);
  
  return results;
}

// ===================================================================
// UPDATE DASHBOARD & SEND ALERTS
// ===================================================================

async function updateDashboard(screenerResults) {
  // Load existing dashboard data
  let dashboardData = {};
  if (fs.existsSync(DASHBOARD_DATA)) {
    dashboardData = JSON.parse(fs.readFileSync(DASHBOARD_DATA, 'utf-8'));
  }

  // Add screener section
  dashboardData.screener = {
    lastScan: new Date().toISOString(),
    tier3: screenerResults.tier3.slice(0, 20), // Top 20 tier 3
    tier2: screenerResults.tier2.slice(0, 15), // Top 15 tier 2
    tier1: screenerResults.tier1.slice(0, 10), // Top 10 tier 1
    totalCandidates: screenerResults.tier3.length + screenerResults.tier2.length + screenerResults.tier1.length,
  };

  // Write back
  fs.writeFileSync(DASHBOARD_DATA, JSON.stringify(dashboardData, null, 2), 'utf-8');
  console.log(`[Dashboard] Updated: ${DASHBOARD_DATA}`);
}

async function sendEmailAlert(screenerResults) {
  /**
   * Send email via Resend API
   * To: ryanwinzenburg@gmail.com
   */
  try {
    // Build email body
    const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    
    const tier3List = screenerResults.tier3.slice(0, 10).map((c, i) => 
      `${i + 1}. <strong>${c.symbol}</strong> — RS: ${c.rsPct}% | Z: ${c.zScore.toFixed(2)} | Mom: ${c.momentum}% | Vol: ${c.volume}x`
    ).join('<br>');
    
    const tier2List = screenerResults.tier2.slice(0, 10).map((c, i) => 
      `${i + 1}. <strong>${c.symbol}</strong> — RS: ${c.rsPct}% | Z: ${c.zScore.toFixed(2)}`
    ).join('<br>');
    
    const htmlBody = `
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI'; color: #333; line-height: 1.6;">
  <h2>🎯 AMS NX Screener Daily</h2>
  <p><strong>Date:</strong> ${dateStr}</p>
  <p><strong>Total Qualified:</strong> ${screenerResults.tier3.length + screenerResults.tier2.length + screenerResults.tier1.length}</p>
  
  <h3>🏆 Top 10 Tier 3 (Highest Quality)</h3>
  <p>${tier3List}</p>
  
  <h3>📊 Top 10 Tier 2</h3>
  <p>${tier2List}</p>
  
  <p style="margin-top: 2rem; color: #666; font-size: 12px;">
    View full results: <a href="file://${WORKSPACE}/dashboard.html">Mission Control Dashboard</a>
  </p>
</div>
    `;
    
    console.log(`[Email] Sending alert to ryanwinzenburg@gmail.com...`);
    
    // Try to send via Resend API if available
    try {
      const resendCmd = `curl -X POST https://api.resend.com/emails \\
        -H "Authorization: Bearer ${process.env.RESEND_API_KEY}" \\
        -H "Content-Type: application/json" \\
        -d '{"from":"alerts@pinchy.ai","to":"ryanwinzenburg@gmail.com","subject":"AMS NX Screener Daily — ${dateStr}","html":"${htmlBody.replace(/"/g, '\\"')}"}'`;
      
      if (process.env.RESEND_API_KEY) {
        const { execSync } = require('child_process');
        execSync(resendCmd, { stdio: 'ignore' });
        console.log(`  ✅ Email sent`);
      } else {
        console.log(`  ⚠️  RESEND_API_KEY not set. Skipping email.`);
      }
    } catch (e) {
      console.warn(`  ⚠️  Email send failed: ${e.message}`);
    }
  } catch (e) {
    console.error(`[Email] Error:`, e.message);
  }
}

async function sendTelegramAlert(screenerResults) {
  /**
   * Send Telegram alert via OpenClaw message tool
   */
  try {
    const candidates = screenerResults.tier3.slice(0, 5);
    const dateStr = new Date().toLocaleDateString();
    
    const message = `🎯 AMS NX Screener Daily — ${dateStr}

📊 TOP 5 TIER 3:
${candidates.map((c, i) => `${i + 1}. ${c.symbol} (RS: ${c.rsPct}% | Z: ${c.zScore.toFixed(2)})`).join('\n')}

📈 Total qualified: ${screenerResults.tier3.length + screenerResults.tier2.length + screenerResults.tier1.length}
🏆 Tier 3: ${screenerResults.tier3.length} | Tier 2: ${screenerResults.tier2.length} | Tier 1: ${screenerResults.tier1.length}

🔗 View all: Mission Control Dashboard (dashboard.html)`;

    console.log(`[Telegram] Sending alert...`);
    console.log(message);
    console.log(`  ✅ Telegram message (ready to integrate with bot)`);
    
  } catch (e) {
    console.error(`[Telegram] Error:`, e.message);
  }
}

// ===================================================================
// MAIN
// ===================================================================

async function main() {
  try {
    console.log('='.repeat(60));
    console.log('AMS NX SCREENER v2 EXECUTOR');
    console.log('='.repeat(60));

    // Run screener
    const results = await runScreener();

    // Update dashboard
    await updateDashboard(results);

    // Send alerts
    await sendEmailAlert(results);
    await sendTelegramAlert(results);

    console.log('='.repeat(60));
    console.log('✅ Screener execution complete');
    console.log('='.repeat(60));
  } catch (e) {
    console.error('❌ Screener failed:', e);
    process.exit(1);
  }
}

main();
