#!/bin/bash

PID_FILE="$(cd "$(dirname "$0")/.." && pwd)/logs/debate-agent.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⏹ Not running"
    exit 0
fi

PID=$(cat "$PID_FILE" 2>/dev/null | tr -d '[:space:]')

if [ -z "$PID" ]; then
    echo "⏹ Not running"
    rm -f "$PID_FILE"
    exit 0
fi

if ! kill -0 "$PID" 2>/dev/null; then
    echo "⏹ Not running"
    rm -f "$PID_FILE"
    exit 0
fi

kill -SIGTERM "$PID" 2>/dev/null

for i in {1..10}; do
    if ! kill -0 "$PID" 2>/dev/null; then
        break
    fi
    sleep 1
done

if kill -0 "$PID" 2>/dev/null; then
    kill -SIGKILL "$PID" 2>/dev/null
    sleep 1
fi

rm -f "$PID_FILE"

echo "✅ Debate-Agent stopped (PID: $PID)"
