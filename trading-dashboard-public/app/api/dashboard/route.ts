import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const snapshotPath = path.join(
      process.cwd(),
      '..',
      'trading',
      'logs',
      'dashboard_snapshot.json'
    );

    if (!fs.existsSync(snapshotPath)) {
      return NextResponse.json(
        { error: 'Dashboard snapshot not found. Run dashboard_data_aggregator.py first.' },
        { status: 404 }
      );
    }

    const data = JSON.parse(fs.readFileSync(snapshotPath, 'utf-8'));
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error reading dashboard snapshot:', error);
    return NextResponse.json(
      { error: 'Failed to load dashboard data' },
      { status: 500 }
    );
  }
}
