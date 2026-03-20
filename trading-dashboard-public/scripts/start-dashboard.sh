#!/usr/bin/env bash
# Start the dashboard from the correct folder (avoids wrong-path npm errors).
# Uses Turbopack + clean .next — helps when Google Drive corrupts Webpack chunks.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "→ Project: $ROOT"
npm run dev:clean:turbo
