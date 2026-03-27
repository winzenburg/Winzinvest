import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';
import { Pool } from 'pg';

const globalForPrisma = globalThis as unknown as {
  prisma?: PrismaClient;
};

function createPrismaClient(): PrismaClient {
  const connectionString =
    process.env.DATABASE_URL ??
    'postgres://user:password@localhost:5432/winzinvest_dummy';

  if (!process.env.DATABASE_URL) {
    // SAFETY: This allows the app to build even when DATABASE_URL is not set,
    // but any auth-related request will fail at query time. Configure a real
    // DATABASE_URL in .env.local for correct behavior.
    // eslint-disable-next-line no-console
    console.warn(
      '[prisma] DATABASE_URL not set; using dummy connection string for build-time operations.',
    );
  }

  const pool = new Pool({ connectionString });
  const adapter = new PrismaPg(pool);

  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === 'development' ? ['error', 'warn'] : ['error'],
  });
}

export const prisma: PrismaClient =
  globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}

