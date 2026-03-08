#!/usr/bin/env node
/**
 * Trading Performance Tracker
 * Tracks daily, weekly, MTD, and YTD P&L returns
 * 
 * Run: node trading/performance-tracker.mjs
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');
const PERFORMANCE_LOG = path.join(WORKSPACE, 'logs/performance-log.json');
const DASHBOARD_DATA = path.join(WORKSPACE, 'public/dashboard-data.json');
const POSITIONS_LOG = path.join(WORKSPACE, 'logs/open-positions.json');

class PerformanceTracker {
  constructor() {
    this.data = this.loadPerformanceLog();
  }

  loadPerformanceLog() {
    try {
      if (fs.existsSync(PERFORMANCE_LOG)) {
        return JSON.parse(fs.readFileSync(PERFORMANCE_LOG, 'utf-8'));
      }
    } catch (e) {
      console.warn(`Failed to load performance log:`, e.message);
    }
    
    return {
      snapshots: [], // Daily snapshots: [{ date, pnl, return }]
      startingValue: 1000000,
      year: new Date().getFullYear(),
    };
  }

  savePerformanceLog() {
    fs.writeFileSync(PERFORMANCE_LOG, JSON.stringify(this.data, null, 2));
  }

  recordSnapshot(pnl, totalValue) {
    /**
     * Record daily P&L snapshot
     */
    const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    
    // Check if we already have a snapshot for today
    const existingIndex = this.data.snapshots.findIndex(s => s.date === today);
    
    const snapshot = {
      date: today,
      pnl: parseFloat(pnl),
      totalValue: parseFloat(totalValue),
      returnPct: ((parseFloat(pnl) / this.data.startingValue) * 100).toFixed(2),
    };
    
    if (existingIndex >= 0) {
      this.data.snapshots[existingIndex] = snapshot;
    } else {
      this.data.snapshots.push(snapshot);
    }
    
    this.savePerformanceLog();
  }

  getReturns() {
    /**
     * Calculate daily, weekly, MTD, and YTD returns
     */
    const today = new Date();
    const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
    const startOfYear = new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0];
    
    // Get last 7 days
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);
    const weekAgoStr = weekAgo.toISOString().split('T')[0];

    if (this.data.snapshots.length === 0) {
      return {
        daily: { pnl: 0, returnPct: 0 },
        weekly: { pnl: 0, returnPct: 0 },
        mtd: { pnl: 0, returnPct: 0 },
        ytd: { pnl: 0, returnPct: 0 },
      };
    }

    // Get today's snapshot
    const todaySnapshot = this.data.snapshots[this.data.snapshots.length - 1];
    const yesterdaySnapshot = this.data.snapshots.length > 1 
      ? this.data.snapshots[this.data.snapshots.length - 2] 
      : null;
    
    // Get first snapshot of week
    const weekStart = this.data.snapshots.find(s => s.date >= weekAgoStr);
    
    // Get first snapshot of month
    const monthStart = this.data.snapshots.find(s => s.date >= startOfMonth);
    
    // Get first snapshot of year
    const yearStart = this.data.snapshots.find(s => s.date >= startOfYear);

    return {
      daily: {
        pnl: (todaySnapshot.pnl - (yesterdaySnapshot?.pnl || 0)).toFixed(2),
        returnPct: ((todaySnapshot.pnl - (yesterdaySnapshot?.pnl || 0)) / this.data.startingValue * 100).toFixed(2),
      },
      weekly: {
        pnl: (todaySnapshot.pnl - (weekStart?.pnl || 0)).toFixed(2),
        returnPct: ((todaySnapshot.pnl - (weekStart?.pnl || 0)) / this.data.startingValue * 100).toFixed(2),
      },
      mtd: {
        pnl: (todaySnapshot.pnl - (monthStart?.pnl || 0)).toFixed(2),
        returnPct: ((todaySnapshot.pnl - (monthStart?.pnl || 0)) / this.data.startingValue * 100).toFixed(2),
      },
      ytd: {
        pnl: (todaySnapshot.pnl - (yearStart?.pnl || 0)).toFixed(2),
        returnPct: ((todaySnapshot.pnl - (yearStart?.pnl || 0)) / this.data.startingValue * 100).toFixed(2),
      },
    };
  }
}

async function updatePerformance() {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`TRADING PERFORMANCE TRACKER`);
  console.log(`${new Date().toLocaleTimeString()}`);
  console.log(`${'='.repeat(60)}\n`);

  const tracker = new PerformanceTracker();

  // Load dashboard data which has current P&L calculated
  let totalPnL = 0;

  try {
    if (fs.existsSync(DASHBOARD_DATA)) {
      const dashboardData = JSON.parse(fs.readFileSync(DASHBOARD_DATA, 'utf-8'));
      
      if (dashboardData.trading && dashboardData.trading.totalPnL) {
        totalPnL = parseFloat(dashboardData.trading.totalPnL);
      }
    }
  } catch (e) {
    console.warn(`Failed to load dashboard data:`, e.message);
  }

  // Record snapshot
  tracker.recordSnapshot(totalPnL, totalValue + 1000000 - totalPnL);
  console.log(`Snapshot recorded: PnL $${totalPnL.toFixed(2)}`);

  // Get returns
  const returns = tracker.getReturns();
  console.log(`\nPERFORMANCE SUMMARY:`);
  console.log(`  Daily:  $${returns.daily.pnl} (${returns.daily.returnPct}%)`);
  console.log(`  Weekly: $${returns.weekly.pnl} (${returns.weekly.returnPct}%)`);
  console.log(`  MTD:    $${returns.mtd.pnl} (${returns.mtd.returnPct}%)`);
  console.log(`  YTD:    $${returns.ytd.pnl} (${returns.ytd.returnPct}%)`);
  console.log(`\n${'='.repeat(60)}\n`);

  // Update dashboard
  try {
    const dashboardData = JSON.parse(fs.readFileSync(DASHBOARD_DATA, 'utf-8'));
    
    dashboardData.performance = {
      lastUpdate: new Date().toISOString(),
      daily: returns.daily,
      weekly: returns.weekly,
      mtd: returns.mtd,
      ytd: returns.ytd,
    };
    
    fs.writeFileSync(DASHBOARD_DATA, JSON.stringify(dashboardData, null, 2));
    console.log('Dashboard updated with performance data.');
  } catch (e) {
    console.warn(`Failed to update dashboard:`, e.message);
  }
}

updatePerformance().catch(console.error);
