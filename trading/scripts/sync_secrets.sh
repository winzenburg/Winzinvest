#!/bin/bash
# Sync secrets from 1Password to secure environment variables

echo "🔐 Syncing trading secrets from 1Password..."

export IB_HOST=$(op read op://Private/"IB Trading API"/host 2>/dev/null || echo "127.0.0.1")
export IB_PORT=$(op read op://Private/"IB Trading API"/port 2>/dev/null || echo "4002")
export IB_CLIENT_ID=$(op read op://Private/"IB Trading API"/client_id 2>/dev/null || echo "101")

echo "✅ Secrets loaded into environment variables"
