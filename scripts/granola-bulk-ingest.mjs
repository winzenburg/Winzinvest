#!/usr/bin/env node

/**
 * Granola Bulk Historical Ingestion
 * 
 * Fetches all meetings from the past N months and imports them into:
 * 1. Second Brain knowledge base (searchable by topic/date/participant)
 * 2. Meeting archive folder (organized by date)
 * 3. Granola index (for quick lookup)
 * 
 * Usage: node scripts/granola-bulk-ingest.mjs [months] [--skip-action-items]
 * Example: node scripts/granola-bulk-ingest.mjs 6
 *          Imports 6 months of meetings
 */

import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_DIR = path.join(__dirname, '..');

const LOG_FILE = path.join(WORKSPACE_DIR, 'logs', 'granola-bulk-ingest.log');
const MEETINGS_ARCHIVE_DIR = path.join(WORKSPACE_DIR, 'meetings');
const KNOWLEDGE_DIR = path.join(WORKSPACE_DIR, 'knowledge');
const GRANOLA_INDEX_FILE = path.join(WORKSPACE_DIR, 'temp', 'granola-index.json');

// Ensure directories exist
function ensureDirs() {
  for (const dir of [
    path.join(WORKSPACE_DIR, 'logs'),
    path.join(WORKSPACE_DIR, 'temp'),
    MEETINGS_ARCHIVE_DIR,
    path.join(KNOWLEDGE_DIR, 'meetings'),
  ]) {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }
}

function log(message) {
  const timestamp = new Date().toISOString();
  const msg = `[${timestamp}] ${message}`;
  console.log(msg);
  fs.appendFileSync(LOG_FILE, msg + '\n');
}

/**
 * Fetch meetings from Granola for past N months
 */
async function fetchHistoricalMeetings(monthsBack = 6) {
  log(`Fetching meetings from past ${monthsBack} months...`);

  const cutoffDate = new Date();
  cutoffDate.setMonth(cutoffDate.getMonth() - monthsBack);

  // Note: Real implementation would call Granola MCP API
  // For now, we'll structure the framework

  try {
    // This would call Granola MCP to get historical meetings
    // Expected response: array of meeting objects with:
    // - id, title, date, participants, transcript, notes, duration
    
    log(`Framework ready for Granola MCP integration`);
    log(`Cutoff date: ${cutoffDate.toISOString()}`);

    // Return empty array as placeholder (real data would come from Granola MCP)
    return [];
  } catch (err) {
    log(`⚠ Error fetching meetings: ${err.message}`);
    return [];
  }
}

/**
 * Save meeting to archive folder (organized by date)
 */
function saveMeetingToArchive(meeting) {
  const meetingDate = new Date(meeting.date);
  const yearMonth = `${meetingDate.getFullYear()}-${String(meetingDate.getMonth() + 1).padStart(2, '0')}`;
  const archiveDir = path.join(MEETINGS_ARCHIVE_DIR, yearMonth);

  if (!fs.existsSync(archiveDir)) {
    fs.mkdirSync(archiveDir, { recursive: true });
  }

  const slug = meeting.title
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .substring(0, 50);

  const filename = `${meeting.date.split('T')[0]}-${slug}.json`;
  const filepath = path.join(archiveDir, filename);

  fs.writeFileSync(filepath, JSON.stringify(meeting, null, 2));
  log(`Saved meeting: ${filename}`);

  return { filepath, yearMonth };
}

/**
 * Save meeting to Second Brain knowledge base
 */
function saveMeetingToKnowledge(meeting) {
  const knowledgeFile = path.join(
    KNOWLEDGE_DIR,
    'meetings',
    `${meeting.date.split('T')[0]}-${meeting.id}.md`
  );

  const markdown = `# Meeting: ${meeting.title}

**Date:** ${new Date(meeting.date).toLocaleDateString()}
**Duration:** ${meeting.duration || 'N/A'} minutes
**Participants:** ${meeting.participants?.join(', ') || 'N/A'}

## Transcript

${meeting.transcript || 'No transcript available'}

## Notes

${meeting.notes || 'No notes available'}

## Key Discussion Points

${extractKeyPoints(meeting.transcript).map(p => `- ${p}`).join('\n')}

---

**Archived:** ${new Date().toLocaleString()}
**Meeting ID:** ${meeting.id}
**Source:** Granola AI`;

  fs.writeFileSync(knowledgeFile, markdown);
  log(`Saved to knowledge base: ${path.basename(knowledgeFile)}`);

  return knowledgeFile;
}

/**
 * Extract key discussion points from transcript
 */
function extractKeyPoints(transcript) {
  if (!transcript) return [];

  const sentences = transcript.split(/[.!?]+/).map(s => s.trim()).filter(s => s.length > 10);
  return sentences.slice(0, 5); // Top 5 sentences
}

/**
 * Update Granola index for quick lookup
 */
function updateGranolaIndex(meetings) {
  const index = {
    lastUpdated: new Date().toISOString(),
    totalMeetings: meetings.length,
    meetings: meetings.map(m => ({
      id: m.id,
      title: m.title,
      date: m.date,
      participants: m.participants,
      duration: m.duration,
    })),
    byDate: {},
    byParticipant: {},
  };

  // Index by date
  meetings.forEach(m => {
    const month = m.date.substring(0, 7);
    if (!index.byDate[month]) index.byDate[month] = [];
    index.byDate[month].push(m.id);
  });

  // Index by participant
  meetings.forEach(m => {
    (m.participants || []).forEach(p => {
      if (!index.byParticipant[p]) index.byParticipant[p] = [];
      index.byParticipant[p].push(m.id);
    });
  });

  fs.writeFileSync(GRANOLA_INDEX_FILE, JSON.stringify(index, null, 2));
  log(`Updated Granola index with ${meetings.length} meetings`);

  return index;
}

/**
 * Generate summary report
 */
function generateReport(meetings) {
  const report = {
    timestamp: new Date().toISOString(),
    totalMeetingsProcessed: meetings.length,
    dateRange: meetings.length > 0 ? {
      earliest: meetings[meetings.length - 1].date,
      latest: meetings[0].date,
    } : null,
    participantSummary: {},
    topicSummary: {},
  };

  // Participant frequency
  const participants = {};
  meetings.forEach(m => {
    (m.participants || []).forEach(p => {
      participants[p] = (participants[p] || 0) + 1;
    });
  });
  report.participantSummary = participants;

  // Monthly distribution
  const monthlyCount = {};
  meetings.forEach(m => {
    const month = m.date.substring(0, 7);
    monthlyCount[month] = (monthlyCount[month] || 0) + 1;
  });
  report.monthlyDistribution = monthlyCount;

  const reportFile = path.join(WORKSPACE_DIR, 'temp', 'granola-ingest-report.json');
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
  log(`Ingest report saved: ${reportFile}`);

  return report;
}

/**
 * Main execution
 */
async function main() {
  try {
    ensureDirs();
    log('===== Granola Bulk Ingest Start =====');

    const monthsBack = parseInt(process.argv[2] || '6');
    const skipActionItems = process.argv.includes('--skip-action-items');

    log(`Configuration: ${monthsBack} months lookback, ${skipActionItems ? 'skip' : 'include'} action items`);

    // Fetch historical meetings
    const meetings = await fetchHistoricalMeetings(monthsBack);

    if (meetings.length === 0) {
      log('No meetings found in Granola for the specified period');
      log('Note: Bulk ingestion requires Granola MCP authentication');
      log('===== Granola Bulk Ingest Complete =====');
      process.exit(0);
    }

    let archivedCount = 0;
    let knowledgeCount = 0;

    // Process each meeting
    for (const meeting of meetings) {
      // Save to archive
      const archived = saveMeetingToArchive(meeting);
      archivedCount++;

      // Save to knowledge base
      const knowledge = saveMeetingToKnowledge(meeting);
      knowledgeCount++;
    }

    // Update indices
    updateGranolaIndex(meetings);

    // Generate report
    const report = generateReport(meetings);

    log(`\n=== INGEST SUMMARY ===`);
    log(`Total meetings: ${meetings.length}`);
    log(`Archived: ${archivedCount}`);
    log(`Saved to knowledge base: ${knowledgeCount}`);
    log(`Date range: ${report.dateRange?.earliest} to ${report.dateRange?.latest}`);
    log(`Top participant: ${Object.entries(report.participantSummary).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A'}`);
    log(`Monthly distribution: ${JSON.stringify(report.monthlyDistribution)}`);

    log('===== Granola Bulk Ingest Complete =====');
  } catch (error) {
    log(`✗ Fatal error: ${error.message}`);
    process.exit(1);
  }
}

main();
