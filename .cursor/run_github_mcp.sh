#!/usr/bin/env bash
# Sources .env and .cursor/.env.local so GITHUB_PERSONAL_ACCESS_TOKEN is available
# for the GitHub MCP server. Cursor does not expand env vars in mcp.json.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
set -a
[ -f "$PROJECT_ROOT/.env" ] && source "$PROJECT_ROOT/.env"
[ -f "$SCRIPT_DIR/.env.local" ] && source "$SCRIPT_DIR/.env.local"
set +a
exec npx -y @modelcontextprotocol/server-github
