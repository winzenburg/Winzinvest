#!/bin/bash
# Send report via both chat and email
# Usage: send_report.sh "Subject" "Body content"

SUBJECT="$1"
BODY="$2"

# Load env vars
if [ -f ~/.openclaw/workspace/.env ]; then
    export $(grep -v '^#' ~/.openclaw/workspace/.env | xargs)
fi

# Send email
cd ~/.openclaw/workspace
python3 scripts/send_email.py \
    --to "$TO_EMAIL" \
    --subject "$SUBJECT" \
    --body "$BODY" \
    > /dev/null 2>&1

# Return success regardless (don't block chat delivery on email failure)
exit 0
