-- AlterTable
ALTER TABLE "Waitlist" 
  ADD COLUMN IF NOT EXISTS "verificationToken" TEXT,
  ADD COLUMN IF NOT EXISTS "verifiedAt" TIMESTAMP(3),
  ALTER COLUMN "status" SET DEFAULT 'unverified';

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "Waitlist_verificationToken_key" ON "Waitlist"("verificationToken");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "Waitlist_verificationToken_idx" ON "Waitlist"("verificationToken");
