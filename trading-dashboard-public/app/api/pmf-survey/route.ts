import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { prisma } from '@/lib/prisma';

const VALID_LEVELS = new Set(['very', 'somewhat', 'not']);

export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  const { disappointmentLevel, idealCustomer, mainBenefit, improvements } = body as Record<string, unknown>;

  if (typeof disappointmentLevel !== 'string' || !VALID_LEVELS.has(disappointmentLevel)) {
    return NextResponse.json({ error: 'Invalid disappointment level' }, { status: 400 });
  }

  try {
    // Get user
    const user = await prisma.user.findUnique({
      where: { email: session.user.email },
      select: { id: true, createdAt: true },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Calculate days active
    const daysActive = Math.floor(
      (Date.now() - user.createdAt.getTime()) / (1000 * 60 * 60 * 24)
    );

    // Save survey response
    await prisma.pmfSurvey.create({
      data: {
        userId: user.id,
        disappointmentLevel,
        idealCustomer: typeof idealCustomer === 'string' ? idealCustomer.trim() || null : null,
        mainBenefit: typeof mainBenefit === 'string' ? mainBenefit.trim() || null : null,
        improvements: typeof improvements === 'string' ? improvements.trim() || null : null,
        daysActive,
      },
    });

    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error('PMF survey error:', err);
    return NextResponse.json({ error: 'Failed to save survey' }, { status: 500 });
  }
}

// Get PMF score for admin dashboard
export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Check if user is admin (you can add role check here)
  const user = await prisma.user.findUnique({
    where: { email: session.user.email },
    select: { role: true },
  });

  if (user?.role !== 'admin') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  }

  try {
    const [total, veryDisappointed, somewhatDisappointed, notDisappointed] = await Promise.all([
      prisma.pmfSurvey.count(),
      prisma.pmfSurvey.count({ where: { disappointmentLevel: 'very' } }),
      prisma.pmfSurvey.count({ where: { disappointmentLevel: 'somewhat' } }),
      prisma.pmfSurvey.count({ where: { disappointmentLevel: 'not' } }),
    ]);

    const pmfScore = total > 0 ? (veryDisappointed / total) * 100 : 0;
    const hasPmf = pmfScore >= 40;

    return NextResponse.json({
      total,
      veryDisappointed,
      somewhatDisappointed,
      notDisappointed,
      pmfScore: Math.round(pmfScore * 10) / 10,
      hasPmf,
      benchmark: 40,
    });
  } catch (err) {
    console.error('PMF score error:', err);
    return NextResponse.json({ error: 'Failed to fetch PMF score' }, { status: 500 });
  }
}
