import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as {
  prisma?: PrismaClient;
};

function createPrismaClient(): PrismaClient {
  if (!process.env.DATABASE_URL) {
    console.warn(
      '[prisma] DATABASE_URL not set; using dummy connection string for build-time operations.',
    );
  }

  return new PrismaClient({
    log: process.env.NODE_ENV === 'development' ? ['error', 'warn'] : ['error'],
  });
}

export const prisma: PrismaClient =
  globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}

