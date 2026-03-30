-- Add activation tracking to User model
ALTER TABLE "User" ADD COLUMN "firstAutomatedTradeAt" TIMESTAMP(3);
ALTER TABLE "User" ADD COLUMN "activationCompletedAt" TIMESTAMP(3);

-- Add referral tracking to Waitlist model
ALTER TABLE "Waitlist" ADD COLUMN "referralCode" TEXT;
ALTER TABLE "Waitlist" ADD COLUMN "referredBy" TEXT;
ALTER TABLE "Waitlist" ADD COLUMN "referralCount" INTEGER NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX "Waitlist_referralCode_key" ON "Waitlist"("referralCode");
CREATE INDEX "Waitlist_referralCode_idx" ON "Waitlist"("referralCode");
CREATE INDEX "Waitlist_referredBy_idx" ON "Waitlist"("referredBy");

-- Create PmfSurvey table
CREATE TABLE "PmfSurvey" (
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

CREATE INDEX "PmfSurvey_userId_idx" ON "PmfSurvey"("userId");
CREATE INDEX "PmfSurvey_disappointmentLevel_idx" ON "PmfSurvey"("disappointmentLevel");
CREATE INDEX "PmfSurvey_createdAt_idx" ON "PmfSurvey"("createdAt");

-- Add foreign key constraint
ALTER TABLE "PmfSurvey" ADD CONSTRAINT "PmfSurvey_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
