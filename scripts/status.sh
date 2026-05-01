#!/usr/bin/env bash

PID_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/logs/debate-agent.pid"
LOG_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/logs/debate-agent.log"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        PORT=$(ps -p "$PID" -o args= | grep -oP '(?<==--port )\d+' || echo "unknown")
        echo "✅ Running (PID: $PID, Port: $PORT)"
        if [ -f "$LOG_FILE" ]; then
            echo "Last 20 log lines:"
            tail -n 20 "$LOG_FILE"
        else
            echo "Log file not found"
        fi
        if [ "${1:-}" = "--follow" ]; then
            tail -f "$LOG_FILE"
        fi
    else
        echo "⏹ Not running"
    fi
else
    echo "⏹ Not running"
fi
