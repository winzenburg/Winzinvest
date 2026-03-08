#!/bin/bash
# Moltbook API Helper Script
# Usage: ./moltbook.sh <command> [args]

set -e

CREDENTIALS_FILE="$HOME/.config/moltbook/credentials.json"
API_BASE="https://www.moltbook.com/api/v1"

# Load API key from credentials file
load_api_key() {
    if [ -f "$CREDENTIALS_FILE" ]; then
        API_KEY=$(jq -r '.api_key' "$CREDENTIALS_FILE")
    else
        echo "❌ No credentials found. Run: $0 register" >&2
        exit 1
    fi
}

# Register a new agent
cmd_register() {
    local name="${1:-Mr. Pinchy}"
    local description="${2:-AI partner focused on building frameworks that turn complex uncertainty into clear, actionable decisions.}"
    
    echo "🦞 Registering agent: $name"
    
    response=$(curl -s -X POST "$API_BASE/agents/register" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$name\", \"description\": \"$description\"}")
    
    echo "$response" | jq .
    
    # Save credentials
    api_key=$(echo "$response" | jq -r '.agent.api_key')
    if [ "$api_key" != "null" ]; then
        mkdir -p "$(dirname "$CREDENTIALS_FILE")"
        echo "{\"api_key\": \"$api_key\", \"agent_name\": \"$name\"}" > "$CREDENTIALS_FILE"
        echo "✅ Credentials saved to $CREDENTIALS_FILE"
        echo "🔗 Claim URL: $(echo "$response" | jq -r '.agent.claim_url')"
        echo "🔑 Verification code: $(echo "$response" | jq -r '.agent.verification_code')"
    fi
}

# Check claim status
cmd_status() {
    load_api_key
    curl -s "$API_BASE/agents/status" \
        -H "Authorization: Bearer $API_KEY" | jq .
}

# Get profile
cmd_profile() {
    load_api_key
    curl -s "$API_BASE/agents/me" \
        -H "Authorization: Bearer $API_KEY" | jq .
}

# Get feed
cmd_feed() {
    load_api_key
    local sort="${1:-hot}"
    local limit="${2:-25}"
    curl -s "$API_BASE/feed?sort=$sort&limit=$limit" \
        -H "Authorization: Bearer $API_KEY" | jq .
}

# Get posts (global)
cmd_posts() {
    load_api_key
    local sort="${1:-hot}"
    local limit="${2:-25}"
    curl -s "$API_BASE/posts?sort=$sort&limit=$limit" \
        -H "Authorization: Bearer $API_KEY" | jq .
}

# Create post
cmd_post() {
    load_api_key
    local submolt="${1:-general}"
    local title="$2"
    local content="$3"
    
    if [ -z "$title" ]; then
        echo "Usage: $0 post <submolt> <title> <content>" >&2
        exit 1
    fi
    
    curl -s -X POST "$API_BASE/posts" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"submolt\": \"$submolt\", \"title\": \"$title\", \"content\": \"$content\"}" | jq .
}

# Create comment
cmd_comment() {
    load_api_key
    local post_id="$1"
    local content="$2"
    
    if [ -z "$content" ]; then
        echo "Usage: $0 comment <post_id> <content> [parent_comment_id]" >&2
        exit 1
    fi
    
    local parent_id="$3"
    local data="{\"content\": \"$content\""
    if [ -n "$parent_id" ]; then
        data="$data, \"parent_id\": \"$parent_id\""
    fi
    data="$data}"
    
    curl -s -X POST "$API_BASE/posts/$post_id/comments" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "$data" | jq .
}

# Upvote post
cmd_upvote() {
    load_api_key
    local post_id="$1"
    curl -s -X POST "$API_BASE/posts/$post_id/upvote" \
        -H "Authorization: Bearer $API_KEY" | jq .
}

# Search
cmd_search() {
    load_api_key
    local query="$1"
    local type="${2:-all}"
    local limit="${3:-20}"
    
    curl -s "$API_BASE/search?q=$(echo "$query" | jq -sRr @uri)&type=$type&limit=$limit" \
        -H "Authorization: Bearer $API_KEY" | jq .
}

# List submolts
cmd_submolts() {
    load_api_key
    curl -s "$API_BASE/submolts" \
        -H "Authorization: Bearer $API_KEY" | jq .
}

# Show help
cmd_help() {
    cat <<EOF
Moltbook CLI Helper

Commands:
  register [name] [description]    Register new agent
  status                           Check claim status
  profile                          Get your profile
  feed [sort] [limit]              Get personalized feed
  posts [sort] [limit]             Get global posts
  post <submolt> <title> <content> Create a post
  comment <post_id> <content>      Add a comment
  upvote <post_id>                 Upvote a post
  search <query> [type] [limit]    Semantic search
  submolts                         List all submolts
  help                             Show this help

Sort options: hot, new, top, rising
Type options: all, posts, comments
EOF
}

# Main dispatcher
case "${1:-help}" in
    register) cmd_register "${@:2}" ;;
    status) cmd_status ;;
    profile) cmd_profile ;;
    feed) cmd_feed "${@:2}" ;;
    posts) cmd_posts "${@:2}" ;;
    post) cmd_post "${@:2}" ;;
    comment) cmd_comment "${@:2}" ;;
    upvote) cmd_upvote "${@:2}" ;;
    search) cmd_search "${@:2}" ;;
    submolts) cmd_submolts ;;
    help|*) cmd_help ;;
esac
