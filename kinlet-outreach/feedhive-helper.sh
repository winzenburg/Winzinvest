#!/bin/bash
# FeedHive MCP Helper Script
# Usage: ./feedhive-helper.sh <action> [args]

set -euo pipefail

FEEDHIVE_API_KEY="${FEEDHIVE_API_KEY:-$(cat /Users/pinchy/.openclaw/workspace/.env.feedhive | grep FEEDHIVE_API_KEY | cut -d= -f2)}"
MCP_ENDPOINT="https://mcp.feedhive.com"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function list_triggers() {
    echo -e "${YELLOW}Listing all FeedHive triggers...${NC}"
    curl -s -X POST "$MCP_ENDPOINT" \
        -H "Authorization: Bearer $FEEDHIVE_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }' | jq '.result.tools[] | {name, description}'
}

function post_twitter() {
    local prompt="$1"
    local scheduled="${2:-}"
    
    echo -e "${YELLOW}Creating Twitter post via FeedHive...${NC}"
    
    local data='{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "trigger_6831n",
            "arguments": {
                "prompt": "'"$prompt"'"'
    
    if [ -n "$scheduled" ]; then
        data+=', "scheduled": "'"$scheduled"'"'
    fi
    
    data+='
            }
        }
    }'
    
    response=$(curl -s -X POST "$MCP_ENDPOINT" \
        -H "Authorization: Bearer $FEEDHIVE_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$data")
    
    if echo "$response" | jq -e '.result' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Post created successfully!${NC}"
        echo "$response" | jq '.result'
    else
        echo -e "${RED}✗ Error creating post:${NC}"
        echo "$response" | jq '.error // .'
        return 1
    fi
}

function show_usage() {
    cat << EOF
Usage: $0 <action> [args]

Actions:
    list                    List all available FeedHive triggers
    twitter <prompt>        Create a Twitter post with AI prompt
    twitter-scheduled <prompt> <ISO-date>
                           Create a scheduled Twitter post

Examples:
    $0 list
    $0 twitter "Share a caregiving insight about sundowning"
    $0 twitter-scheduled "Monday motivation for caregivers" "2026-02-10T09:00:00Z"

Environment:
    FEEDHIVE_API_KEY       FeedHive API key (auto-loaded from .env.feedhive)
EOF
}

# Main
case "${1:-}" in
    list)
        list_triggers
        ;;
    twitter)
        if [ -z "${2:-}" ]; then
            echo -e "${RED}Error: Prompt required${NC}"
            show_usage
            exit 1
        fi
        post_twitter "$2"
        ;;
    twitter-scheduled)
        if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
            echo -e "${RED}Error: Both prompt and scheduled date required${NC}"
            show_usage
            exit 1
        fi
        post_twitter "$2" "$3"
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
