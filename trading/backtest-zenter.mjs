#!/usr/bin/env node
/**
 * PHASE 2 INSIGHT 5 BACKTEST: zEnter Parameter Optimization
 * 
 * Tests multiple zEnter thresholds (40, 45, 50, 55) and compares:
 * - Number of qualified candidates (volume of opportunities)
 * - Average win rate vs average loser size (expectancy ratio)
 * - Maximum single-trade return (right tail capture)
 * 
 * Key Principle: Optimize for expectancy ratio, NOT win rate
 * "Campbell & Co. system profitable only 56% of months but 100% of 4-year windows"
 * 
 * Usage: node trading/backtest-zenter.mjs
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');

// Test parameters
const ZENTER_VALUES = [40, 45, 50, 55];
const TEST_DATA_FILE = path.join(WORKSPACE, 'backtest-data', 'test-positions.json');

console.log(`
${'='.repeat(70)}
PHASE 2 INSIGHT 5: zEnter Parameter Backtest
${'='.repeat(70)}

Testing hypothesis: Lower zEnter (more trades) = better expectancy ratio

Parameters to test: ${ZENTER_VALUES.join(', ')}

Key Metrics:
  - Qualified Candidates: Volume of trading opportunities
  - Win Rate: % of winning trades (optimize for >55%, but NOT primary)
  - Avg Winner / Avg Loser: Expectancy ratio (PRIMARY METRIC)
  - Max Trade Return: Right tail capture (should improve with lower zEnter)
  - Sharpe Ratio: Risk-adjusted returns (overall performance)

Covel Principle:
  "The 56% win rate of Campbell & Co. is irrelevant compared to their winners
   being 3-4x larger than their losers. This asymmetry funds everything."

Instructions for backtesting:
  1. Run screener with zEnter = 50 (current): node trading/screener-executor.mjs
  2. Record qualified Tier 3 candidates (baseline)
  3. Update PHASE2_CONFIG.zEnter = 40 in screener-executor.mjs
  4. Run screener with zEnter = 40: node trading/screener-executor.mjs
  5. Compare candidate counts and composition
  6. For each configuration, run engine and analyze positions over 3-6 months
  7. Calculate: win rate, avg winner, avg loser, expectancy ratio
  8. Choose configuration with best expectancy ratio (not win rate)

${'='.repeat(70)}
`);

// Placeholder: Historical position data would be loaded here
// For now, provide framework for manual data entry

const BACKTEST_TEMPLATE = {
  zEnter: 50,
  period: '2026-02-24 to 2026-08-24', // Suggested 6-month backtest
  qualifiedCandidates: 0,
  trades: [],
  summary: {
    totalTrades: 0,
    winningTrades: 0,
    losingTrades: 0,
    winRate: 0,
    avgWinner: 0,
    avgLoser: 0,
    expectancyRatio: 0,
    maxReturn: 0,
    totalPnL: 0,
    sharpeRatio: 0,
  }
};

function calculateMetrics(trades) {
  if (!trades || trades.length === 0) {
    return { ...BACKTEST_TEMPLATE.summary };
  }

  const winners = trades.filter(t => t.pnlPct > 0);
  const losers = trades.filter(t => t.pnlPct < 0);

  const avgWinner = winners.length > 0
    ? winners.reduce((sum, t) => sum + t.pnlPct, 0) / winners.length
    : 0;

  const avgLoser = losers.length > 0
    ? losers.reduce((sum, t) => sum + t.pnlPct, 0) / losers.length
    : 0;

  const expectancyRatio = Math.abs(avgLoser) > 0 ? avgWinner / Math.abs(avgLoser) : 0;
  const maxReturn = Math.max(...trades.map(t => t.pnlPct), 0);
  const totalPnL = trades.reduce((sum, t) => sum + t.pnl, 0);
  const winRate = (winners.length / trades.length) * 100;

  // Simplified Sharpe (requires daily returns for proper calc)
  const returns = trades.map(t => t.pnlPct / 100);
  const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - meanReturn, 2), 0) / returns.length;
  const sharpeRatio = (meanReturn / Math.sqrt(variance)) * Math.sqrt(252); // Annualized

  return {
    totalTrades: trades.length,
    winningTrades: winners.length,
    losingTrades: losers.length,
    winRate: parseFloat(winRate.toFixed(1)),
    avgWinner: parseFloat(avgWinner.toFixed(2)),
    avgLoser: parseFloat(avgLoser.toFixed(2)),
    expectancyRatio: parseFloat(expectancyRatio.toFixed(2)),
    maxReturn: parseFloat(maxReturn.toFixed(2)),
    totalPnL: parseFloat(totalPnL.toFixed(2)),
    sharpeRatio: isNaN(sharpeRatio) ? 0 : parseFloat(sharpeRatio.toFixed(2)),
  };
}

function generateBacktestReport() {
  console.log(`
${'='.repeat(70)}
BACKTEST COMPARISON TEMPLATE
${'='.repeat(70)}

Once you have 3-6 months of trading data with different zEnter values,
fill in the actual trade results and run this analysis:

`);

  const results = ZENTER_VALUES.map(zEnter => ({
    zEnter,
    config: BACKTEST_TEMPLATE,
    metrics: calculateMetrics(BACKTEST_TEMPLATE.trades),
  }));

  // Create table
  console.log(`
zEnter | Candidates | Win Rate | Avg Win | Avg Loss | Ratio | Max Return | Sharpe | Total P&L
-------|------------|----------|---------|----------|-------|------------|--------|----------
`);

  results.forEach(r => {
    console.log(
      `${r.zEnter}    | ${String(r.config.qualifiedCandidates).padStart(10)} | ` +
      `${String(r.metrics.winRate.toFixed(1) + '%').padStart(8)} | ` +
      `${String(r.metrics.avgWinner.toFixed(2)).padStart(7)} | ` +
      `${String(r.metrics.avgLoser.toFixed(2)).padStart(8)} | ` +
      `${String(r.metrics.expectancyRatio.toFixed(2)).padStart(5)} | ` +
      `${String(r.metrics.maxReturn.toFixed(2) + '%').padStart(10)} | ` +
      `${String(r.metrics.sharpeRatio.toFixed(2)).padStart(6)} | ` +
      `${String(r.metrics.totalPnL.toFixed(2)).padStart(9)}`
    );
  });

  console.log(`

KEY INSIGHT:
Look for the zEnter value with the HIGHEST expectancy ratio (Avg Win / |Avg Loss|),
NOT the highest win rate.

Example interpretation:
  - zEnter 50 (conservative): 65% win rate, +2.5% avg winner, -1.8% avg loser → Ratio: 1.39
  - zEnter 40 (aggressive): 52% win rate, +5.2% avg winner, -2.1% avg loser → Ratio: 2.48

Choose zEnter 40 even with 52% win rate, because expectancy is 1.78x higher.
Over 100 trades, the geometric mean return compounds dramatically better.

${'='.repeat(70)}

IMPLEMENTATION:
Once you identify the optimal zEnter, update PHASE2_CONFIG in screener-executor.mjs:
  PHASE2_CONFIG.zEnter = [optimal_value]; // e.g., 40 or 45
Then commit the change.

${'='.repeat(70)}
`);
}

// Run report
generateBacktestReport();
