import { config } from 'dotenv';
import { defineConfig } from 'prisma/config';
import { resolve } from 'path';

config({ path: resolve(__dirname, '.env.local') });

export default defineConfig({
  schema: 'prisma/schema.prisma',
  datasource: {
    url: process.env.DATABASE_URL || 'postgresql://dummy:dummy@dummy:5432/dummy?sslmode=require',
  },
});

