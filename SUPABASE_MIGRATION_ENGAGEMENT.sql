-- ============================================================================
-- SUPABASE MIGRATION — Engagement & Personalization Features
-- ============================================================================
-- Run this in Supabase SQL Editor to add engagement tracking columns.
-- Safe to run multiple times (idempotent).
-- ============================================================================

-- Add engagement tracking columns to User table
ALTER TABLE "User" 
ADD COLUMN IF NOT EXISTS "lastDashboardViewAt" TIMESTAMP(3),
ADD COLUMN IF NOT EXISTS "dashboardViewCount" INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS "preferredViewDepth" TEXT DEFAULT 'overview',
ADD COLUMN IF NOT EXISTS "emailFrequency" TEXT DEFAULT 'weekly',
ADD COLUMN IF NOT EXISTS "engagementSegment" TEXT;

-- Set default values for existing users
UPDATE "User" 
SET "dashboardViewCount" = 0 
WHERE "dashboardViewCount" IS NULL;

-- Create index for efficient segmentation queries
CREATE INDEX IF NOT EXISTS "User_engagementSegment_idx" 
ON "User"("engagementSegment");

-- ============================================================================
-- Expected segments (for reference):
-- - nervous_monitor: Checks multiple times per day
-- - daily_checker: Once per day, consistent
-- - weekly_checker: 2-4 times per week
-- - monthly_reviewer: < 1 per week
-- ============================================================================
