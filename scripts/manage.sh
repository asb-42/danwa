#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

case "$1" in
    start)
        bash "$PROJECT_DIR/scripts/start.sh"
        ;;
    stop)
        bash "$PROJECT_DIR/scripts/stop.sh"
        ;;
    status)
        bash "$PROJECT_DIR/scripts/status.sh"
        ;;
    logs)
        tail -f "$PROJECT_DIR/logs/debate-agent.log"
        ;;
    trace)
        tail -f "$PROJECT_DIR/logs/$(ls -t "$PROJECT_DIR/logs" | head -n 1)"
        ;;
    backup)
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_DIR="$HOME/backups/debate-agent/$TIMESTAMP"
        mkdir -p "$BACKUP_DIR"
        cp -r "$PROJECT_DIR/logs" "$BACKUP_DIR/"
        cp -r "$PROJECT_DIR/memory" "$BACKUP_DIR/"
        cp "$PROJECT_DIR/config/llm_profiles.yaml" "$BACKUP_DIR/"
        echo "📦 Backup erstellt: $BACKUP_DIR"
        ;;
    cleanup)
        bash "$PROJECT_DIR/scripts/cleanup.sh"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs|cleanup|backup}"
        exit 1
        ;;
esac