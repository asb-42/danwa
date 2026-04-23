#!/usr/bin/env bash
set -e

SERVICE_NAME="debate-agent@$(whoami)"
PROJECT_DIR="$HOME/projects/debate-agent"

case "$1" in
    install)
        ln -sf "$PROJECT_DIR/systemd/debate-agent.service" "$HOME/.config/systemd/user/"
        systemctl --user daemon-reload
        systemctl --user enable --now "$SERVICE_NAME"
        echo "✅ Service aktiviert. Status: systemctl --user status $SERVICE_NAME"
        ;;
    status)
        systemctl --user status "$SERVICE_NAME"
        ;;
    logs)
        journalctl --user -u "$SERVICE_NAME" -f --no-pager
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
    stop)
        systemctl --user stop "$SERVICE_NAME"
        ;;
    restart)
        systemctl --user restart "$SERVICE_NAME"
        ;;
    *)
        echo "Usage: $0 {install|status|logs|trace|backup|stop|restart}"
        exit 1
        ;;
esac