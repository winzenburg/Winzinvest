#!/bin/bash

# Start webhook listener with environment variables loaded
cd "$(dirname "$0")/.."

# Load .env file
export $(grep -v '^#' .env | xargs)

# Start the webhook listener
python3 scripts/webhook_listener.py
