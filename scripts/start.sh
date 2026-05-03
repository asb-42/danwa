#!/bin/bash

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$LOG_DIR/debate-agent.pid"
LOG_FILE="$LOG_DIR/debate-agent.log"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null | tr -d '[:space:]')
    if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
        echo "Error: Debate-Agent already running (PID: $PID)"
        exit 1
    fi
    # Stale PID file — process is gone, clean up
    rm -f "$PID_FILE"
fi

mkdir -p "$LOG_DIR"

PORT="${PORT:-7860}"

cd "$PROJECT_DIR" || exit 1

export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
nohup uv run uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" > "$LOG_FILE" 2>&1 &
APP_PID=$!
echo "$APP_PID" > "$PID_FILE"

sleep 2

if ps -p "$APP_PID" > /dev/null 2>&1; then
    echo "✅ Debate-Agent started on port $PORT (PID: $APP_PID). Logs: logs/debate-agent.log"
else
    echo "❌ Failed to start. Check logs: logs/debate-agent.log"
    rm -f "$PID_FILE"
    exit 1
fi
