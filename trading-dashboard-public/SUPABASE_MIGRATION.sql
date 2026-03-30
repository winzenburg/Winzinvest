-- ============================================================================
-- Growth Features Migration for Supabase
-- Run this in Supabase Dashboard → SQL Editor
-- ============================================================================

-- 1. Add activation tracking to User table
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "firstAutomatedTradeAt" TIMESTAMP(3);
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "activationCompletedAt" TIMESTAMP(3);

-- 2. Add referral tracking to Waitlist table
ALTER TABLE "Waitlist" ADD COLUMN IF NOT EXISTS "referralCode" TEXT;
ALTER TABLE "Waitlist" ADD COLUMN IF NOT EXISTS "referredBy" TEXT;
ALTER TABLE "Waitlist" ADD COLUMN IF NOT EXISTS "referralCount" INTEGER NOT NULL DEFAULT 0;

-- 3. Create indexes for referral lookups
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'Waitlist_referralCode_key') THEN
        CREATE UNIQUE INDEX "Waitlist_referralCode_key" ON "Waitlist"("referralCode");
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'Waitlist_referralCode_idx') THEN
        CREATE INDEX "Waitlist_referralCode_idx" ON "Waitlist"("referralCode");
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'Waitlist_referredBy_idx') THEN
        CREATE INDEX "Waitlist_referredBy_idx" ON "Waitlist"("referredBy");
    END IF;
END $$;

-- 4. Create PmfSurvey table
CREATE TABLE IF NOT EXISTS "PmfSurvey" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "disappointmentLevel" TEXT NOT NULL,
    "idealCustomer" TEXT,
    "mainBenefit" TEXT,
    "improvements" TEXT,
    "daysActive" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PmfSurvey_pkey" PRIMARY KEY ("id")
);

-- 5. Create indexes for PmfSurvey
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'PmfSurvey_userId_idx') THEN
        CREATE INDEX "PmfSurvey_userId_idx" ON "PmfSurvey"("userId");
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'PmfSurvey_disappointmentLevel_idx') THEN
        CREATE INDEX "PmfSurvey_disappointmentLevel_idx" ON "PmfSurvey"("disappointmentLevel");
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'PmfSurvey_createdAt_idx') THEN
        CREATE INDEX "PmfSurvey_createdAt_idx" ON "PmfSurvey"("createdAt");
    END IF;
END $$;

-- 6. Add foreign key constraint (if not exists)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'PmfSurvey_userId_fkey'
    ) THEN
        ALTER TABLE "PmfSurvey" ADD CONSTRAINT "PmfSurvey_userId_fkey" 
            FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;

-- 7. Backfill referral codes for existing waitlist entries
UPDATE "Waitlist"
SET "referralCode" = UPPER(SUBSTRING(MD5(RANDOM()::text) FROM 1 FOR 8))
WHERE "referralCode" IS NULL;

-- 8. Verify migration succeeded
SELECT 
    'User columns' as check_type,
    COUNT(*) FILTER (WHERE column_name = 'firstAutomatedTradeAt') as first_trade_column,
    COUNT(*) FILTER (WHERE column_name = 'activationCompletedAt') as activation_column
FROM information_schema.columns
WHERE table_name = 'User'

UNION ALL

SELECT 
    'Waitlist columns',
    COUNT(*) FILTER (WHERE column_name = 'referralCode'),
    COUNT(*) FILTER (WHERE column_name = 'referredBy')
FROM information_schema.columns
WHERE table_name = 'Waitlist'

UNION ALL

SELECT 
    'PmfSurvey table',
    COUNT(*),
    NULL
FROM information_schema.tables
WHERE table_name = 'PmfSurvey';

-- Expected output:
--  check_type        | first_trade_column | activation_column
-- -------------------+--------------------+-------------------
--  User columns      | 1                  | 1
--  Waitlist columns  | 1                  | 1
--  PmfSurvey table   | 1                  | null
