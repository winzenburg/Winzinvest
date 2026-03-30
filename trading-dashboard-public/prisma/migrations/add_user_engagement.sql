-- Add engagement tracking columns to users table

ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "lastDashboardViewAt" TIMESTAMP(3);
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "dashboardViewCount" INTEGER NOT NULL DEFAULT 0;
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "preferredViewDepth" TEXT DEFAULT 'overview';
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "emailFrequency" TEXT DEFAULT 'weekly';
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "engagementSegment" TEXT;

-- Create index for engagement queries
CREATE INDEX IF NOT EXISTS "User_engagementSegment_idx" ON "User"("engagementSegment");
