#!/bin/bash
# Voice Note Transcription Pipeline
# Usage: transcribe-voice-note.sh /path/to/audio.m4a
# Outputs: /path/to/audio.txt (transcript)
# Then optionally triggers market research based on content

set -e

AUDIO_FILE="${1}"
OPENAI_API_KEY="${OPENAI_API_KEY:?OPENAI_API_KEY not set}"

if [ ! -f "$AUDIO_FILE" ]; then
  echo "Error: Audio file not found: $AUDIO_FILE"
  exit 1
fi

TRANSCRIPT_FILE="${AUDIO_FILE%.*}.txt"
RESEARCH_TRIGGER_FILE="${AUDIO_FILE%.*}.research"

echo "Transcribing: $AUDIO_FILE"

# Call OpenAI Whisper API
curl -s -X POST "https://api.openai.com/v1/audio/transcriptions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F "file=@$AUDIO_FILE" \
  -F "model=whisper-1" \
  -F "language=en" | jq -r '.text' > "$TRANSCRIPT_FILE"

echo "✅ Transcript saved to: $TRANSCRIPT_FILE"
cat "$TRANSCRIPT_FILE"

# If transcript contains "research", suggest triggering market research
if grep -qi "research\|market\|analyze\|survey" "$TRANSCRIPT_FILE"; then
  echo ""
  echo "🔍 Detected research request. To trigger market research:"
  echo "   sessions_send --message \"$(cat $TRANSCRIPT_FILE)\""
fi
