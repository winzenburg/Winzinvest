#!/bin/bash

# Wrapper script for cron jobs that need both Telegram and email delivery
# Usage: send-with-email.sh "<subject>" "<message>"

SUBJECT="$1"
MESSAGE="$2"

if [ -z "$SUBJECT" ] || [ -z "$MESSAGE" ]; then
    echo "Usage: $0 \"subject\" \"message\""
    exit 1
fi

# Send email
~/.openclaw/workspace/scripts/send-email.sh "$SUBJECT" "$MESSAGE"
EMAIL_RESULT=$?

if [ $EMAIL_RESULT -eq 0 ]; then
    echo "Email sent. Now output for Telegram:"
    echo "$MESSAGE"
else
    echo "⚠️ Email failed to send, but continuing with Telegram delivery"
    echo "$MESSAGE"
fi

exit 0
