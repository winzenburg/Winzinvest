#!/bin/bash

# Email sender using Resend API
# Usage: ./send-email.sh "subject" "content"

RESEND_API_KEY="${RESEND_API_KEY:-re_UjAL42UD_N8hqtA5k5G8w7HUxxx2nFwCv}"
TO_EMAIL="${TO_EMAIL:-ryanwinzenburg@gmail.com}"
FROM_EMAIL="Mr. Pinchy <onboarding@resend.dev>"

SUBJECT="$1"
CONTENT="$2"

if [ -z "$SUBJECT" ] || [ -z "$CONTENT" ]; then
    echo "Usage: $0 \"subject\" \"content\""
    exit 1
fi

# Create temp file for JSON payload
TMPFILE=$(mktemp)
cat > "$TMPFILE" <<EOF
{
  "from": "$FROM_EMAIL",
  "to": ["$TO_EMAIL"],
  "subject": "$SUBJECT",
  "text": "$CONTENT"
}
EOF

# Send email
RESPONSE=$(curl -s -X POST 'https://api.resend.com/emails' \
  -H "Authorization: Bearer $RESEND_API_KEY" \
  -H 'Content-Type: application/json' \
  -d @"$TMPFILE")

# Cleanup
rm "$TMPFILE"

# Check result
if echo "$RESPONSE" | grep -q '"id"'; then
    EMAIL_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    echo "✅ Email sent successfully!"
    echo "Email ID: $EMAIL_ID"
    exit 0
else
    echo "❌ Failed to send email"
    echo "$RESPONSE"
    exit 1
fi
