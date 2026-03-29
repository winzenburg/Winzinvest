import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';

export async function GET() {
  try {
    console.log('[db-health] Starting health check');
    console.log('[db-health] DATABASE_URL exists:', !!process.env.DATABASE_URL);
    console.log('[db-health] DATABASE_URL prefix:', process.env.DATABASE_URL?.substring(0, 40));
    
    // Try a simple query
    const result = await prisma.$queryRaw`SELECT 1 as health`;
    console.log('[db-health] Query successful:', result);
    
    return NextResponse.json({
      status: 'healthy',
      database: 'connected',
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    console.error('[db-health] Error:', err);
    console.error('[db-health] Error name:', (err as Error).name);
    console.error('[db-health] Error message:', (err as Error).message);
    console.error('[db-health] Error stack:', (err as Error).stack);
    
    return NextResponse.json(
      {
        status: 'unhealthy',
        error: (err as Error).message,
        name: (err as Error).name,
      },
      { status: 500 },
    );
  }
}
