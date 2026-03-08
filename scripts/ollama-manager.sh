#!/bin/bash

# Ollama Manager Script
# Start/stop Ollama server, manage models, check status

set -e

OLLAMA_HOST="127.0.0.1:11434"
OLLAMA_URL="http://$OLLAMA_HOST"

function print_header() {
    echo ""
    echo "🤖 Ollama Manager"
    echo "=================="
    echo ""
}

function check_ollama_running() {
    if curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        echo "✅ Ollama is running (127.0.0.1:11434)"
        return 0
    else
        echo "❌ Ollama is not running"
        return 1
    fi
}

function start_ollama() {
    print_header
    echo "Starting Ollama..."
    echo ""
    echo "ℹ️  Ollama will run in this terminal. Open a new terminal for other commands."
    echo "ℹ️  You can access the API at: http://127.0.0.1:11434"
    echo ""
    
    ollama serve
}

function stop_ollama() {
    print_header
    echo "Stopping Ollama..."
    pkill -f "ollama serve" || echo "Ollama not running"
    sleep 2
    
    if check_ollama_running; then
        echo "⚠️  Ollama still running, try again or use: pkill -9 ollama"
    else
        echo "✅ Ollama stopped"
    fi
}

function list_models() {
    print_header
    
    if ! check_ollama_running; then
        echo "Start Ollama first: ollama serve"
        exit 1
    fi
    
    echo "Downloaded Models:"
    echo ""
    curl -s "$OLLAMA_URL/api/tags" | jq '.models[] | "\(.name) - \(.size | . / 1073741824 | round | . + " GB")"' || echo "❌ Failed to fetch models"
}

function test_model() {
    print_header
    
    if ! check_ollama_running; then
        echo "Start Ollama first: ollama serve"
        exit 1
    fi
    
    MODEL=${1:-"mistral"}
    PROMPT=${2:-"What is swing trading in 2 sentences?"}
    
    echo "Testing model: $MODEL"
    echo "Prompt: $PROMPT"
    echo ""
    echo "Generating response..."
    echo ""
    
    curl -s "$OLLAMA_URL/api/generate" -d "{
        \"model\": \"$MODEL\",
        \"prompt\": \"$PROMPT\",
        \"stream\": false
    }" | jq '.response'
}

function pull_model() {
    print_header
    
    MODEL=${1:-"mistral"}
    
    echo "Pulling model: $MODEL"
    echo ""
    
    ollama pull "$MODEL"
}

function show_usage() {
    echo ""
    echo "Usage: bash scripts/ollama-manager.sh [command] [args]"
    echo ""
    echo "Commands:"
    echo "  start              Start Ollama server"
    echo "  stop               Stop Ollama server"
    echo "  status             Check if Ollama is running"
    echo "  list               List downloaded models"
    echo "  test [model]       Test a model with a sample prompt"
    echo "  pull [model]       Download a new model"
    echo ""
    echo "Examples:"
    echo "  bash scripts/ollama-manager.sh start"
    echo "  bash scripts/ollama-manager.sh test mistral"
    echo "  bash scripts/ollama-manager.sh pull neural-chat"
    echo ""
}

# Main
COMMAND=${1:-"status"}

case "$COMMAND" in
    start)
        start_ollama
        ;;
    stop)
        stop_ollama
        ;;
    status)
        print_header
        check_ollama_running
        ;;
    list)
        list_models
        ;;
    test)
        test_model "$2" "$3"
        ;;
    pull)
        pull_model "$2"
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
