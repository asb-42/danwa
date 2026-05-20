#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
#  manage.sh — Danwa Gesamt-Management (Backend + Frontend)
#
#  Verwendung:
#    ./manage.sh              # interaktives Menü
#    ./manage.sh start        # Backend UND Frontend starten
#    ./manage.sh start fe     # nur Frontend starten
#    ./manage.sh start be     # nur Backend starten
#    ./manage.sh stop         # alles stoppen
#    ./manage.sh status       # Status anzeigen
#    ./manage.sh logs         # Live-Logs (Backend + Frontend)
#    ./manage.sh logs be      # nur Backend-Logs
#    ./manage.sh logs fe      # nur Frontend-Logs
#    ./manage.sh restart      # alles neu starten
#    ./manage.sh clean        # Caches & Logs aufräumen
# ─────────────────────────────────────────────────────────────────────
set -uo pipefail
# NOTE: -u (nounset) entfernt, da PYTHONPATH ggf. nicht gesetzt ist.
# Stattdessen verwenden wir ${VAR:-} überall.

# ═══════════════════════════════════════════════════════════════════════
# Konfiguration
# ═══════════════════════════════════════════════════════════════════════

# Robuste Projektpfad-Erkennung (funktioniert auch bei Symlinks,
# Aufruf ohne ./ und aus anderen Verzeichnissen heraus)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
FE_DIR="$PROJECT_DIR/frontend"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/pids"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FE_PID_FILE="$PID_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FE_LOG="$LOG_DIR/frontend.log"

BACKEND_PORT="${BACKEND_PORT:-7860}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

mkdir -p "$LOG_DIR" "$PID_DIR"

# ═══════════════════════════════════════════════════════════════════════
# Farben & Formatierung
# ═══════════════════════════════════════════════════════════════════════
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'
BOLD='\033[1m'; RESET='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${RESET}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*"; }
log_step()    { echo -e "\n${BOLD}${MAGENTA}▸ $*${RESET}"; }
log_header()  { echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════${RESET}"; echo -e "${BOLD}${CYAN}  $*${RESET}"; echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${RESET}"; }

# ═══════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ═══════════════════════════════════════════════════════════════════════

check_node_version() {
    local required_major="${1:-22}"
    if command -v node &>/dev/null; then
        local current_version
        current_version="$(node --version | sed 's/^v//')"
        local current_major
        current_major="${current_version%%.*}"
        if [[ "$current_major" -lt "$required_major" ]]; then
            log_error "Node.js >= $required_major erforderlich (installiert: $current_version)"
            log_info "Installiere: nvm install $required_major"
            return 1
        fi
        return 0
    else
        log_error "Node.js nicht installiert"
        return 1
    fi
}

pid_running() {
    local pid_file="$1"; shift
    if [[ -f "$pid_file" ]]; then
        local pid
        pid="$(cat "$pid_file" 2>/dev/null | tr -d '[:space:]')"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
    fi
    return 1
}

backend_running()  { pid_running "$BACKEND_PID_FILE"; }
frontend_running() { pid_running "$FE_PID_FILE"; }

wait_for_url() {
    local url="$1" timeout="${2:-30}"
    local elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        if curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null | grep -qE '^[2345][0-9][0-9]$'; then
            return 0
        fi
        sleep 0.5
        elapsed=$(( elapsed + 1 ))
    done
    return 1
}

# ═══════════════════════════════════════════════════════════════════════
# Backend
# ═══════════════════════════════════════════════════════════════════════

start_backend() {
    log_step "Backend starten …"
    if backend_running &>/dev/null; then
        log_warn "Backend läuft bereits (PID: $(backend_running))"
        return 0
    fi

    cd "$PROJECT_DIR"
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
    export UV_PYTHONPATH="${PROJECT_DIR}:${UV_PYTHONPATH:-}"
    export PATH="$HOME/.local/bin:$PATH"
    nohup uv run uvicorn backend.main:app \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        --log-level info \
        > "$BACKEND_LOG" 2>&1 &

    local pid=$!
    echo "$pid" > "$BACKEND_PID_FILE"
    echo "$pid" > "$LOG_DIR/backend_recent.pid"

    if wait_for_url "http://localhost:$BACKEND_PORT/docs" 120; then
        log_ok "Backend gestartet (PID: $pid) → http://localhost:$BACKEND_PORT"
    else
        log_warn "Backend-Start dauert länger als erwartet — prüfe Logs mit: ./manage.sh logs be"
    fi
}

stop_backend() {
    log_step "Backend stoppen …"
    local pid
    pid="$(backend_running 2>/dev/null)" || true
    if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null && sleep 1
        # SIGKILL falls nötig
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
        rm -f "$BACKEND_PID_FILE"
        log_ok "Backend (PID: $pid) gestoppt"
    else
        log_warn "Backend läuft nicht"
    fi

    # Aufräumen: eventuelle uvicorn-Prozesse für dieses Projekt
    pkill -f "uvicorn backend.main" 2>/dev/null || true
}

# ═══════════════════════════════════════════════════════════════════════
# Frontend
# ═══════════════════════════════════════════════════════════════════════

start_frontend() {
    log_step "Frontend starten …"
    if frontend_running &>/dev/null; then
        log_warn "Frontend läuft bereits (PID: $(frontend_running))"
        return 0
    fi

    cd "$FE_DIR"
    nohup npm run dev -- --port "$FRONTEND_PORT" \
        > "$FE_LOG" 2>&1 &

    local pid=$!
    echo "$pid" > "$FE_PID_FILE"

    if wait_for_url "http://localhost:$FRONTEND_PORT" 60; then
        log_ok "Frontend gestartet (PID: $pid) → http://localhost:$FRONTEND_PORT"
    else
        log_warn "Frontend-Start dauert länger als erwartet — prüfe Logs mit: ./manage.sh logs fe"
    fi
}

stop_frontend() {
    log_step "Frontend stoppen …"
    local pid
    pid="$(frontend_running 2>/dev/null)" || true
    if [[ -n "$pid" ]]; then
        # Gesamte Prozessgruppe beenden (erfasst auch Vite-Kindprozesse)
        kill -- -"$pid" 2>/dev/null
        sleep 1
        # SIGKILL falls nötig
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            sleep 1
        fi
        rm -f "$FE_PID_FILE"
        log_ok "Frontend (PID: $pid) gestoppt"
    else
        log_warn "Frontend läuft nicht"
    fi

    # Fallback: eventuell übrig gebliebene Vite-Prozesse beenden
    pkill -f "vite" 2>/dev/null || true
}

# ═══════════════════════════════════════════════════════════════════════
# Logs
# ═══════════════════════════════════════════════════════════════════════

show_logs() {
    local target="${1:-all}"
    case "$target" in
        be|backend)
            log_header "Backend-Logs (tail -f) — Ctrl+C zum Beenden"
            tail -f "$BACKEND_LOG"
            ;;
        fe|frontend)
            log_header "Frontend-Logs (tail -f) — Ctrl+C zum Beenden"
            tail -f "$FE_LOG"
            ;;
        all|*)
            log_header "Live-Logs: Backend + Frontend (Ctrl+C zum Beenden)"
            tail -f "$BACKEND_LOG" "$FE_LOG" || true
            ;;
    esac
}

show_status() {
    log_header "Danwa — Systemstatus"

    echo ""
    echo -e "  ${BOLD}Backend:${RESET}"
    if backend_running &>/dev/null; then
        local bp
        bp="$(backend_running)"
        echo -e "    Status:  ${GREEN}aktiv${RESET} (PID: $bp)"
        echo -e "    Port:    $BACKEND_PORT"
        echo -e "    Log:     $BACKEND_LOG"
        if [[ -f "$LOG_DIR/backend_recent.pid" ]]; then
            echo -e "    Uptime:  $(ps -o etime= -p "$bp" 2>/dev/null | xargs || echo '?')"
        fi
    else
        echo -e "    Status:  ${RED}gestoppt${RESET}"
    fi

    echo ""
    echo -e "  ${BOLD}Frontend:${RESET}"
    if frontend_running &>/dev/null; then
        local fp
        fp="$(frontend_running)"
        echo -e "    Status:  ${GREEN}aktiv${RESET} (PID: $fp)"
        echo -e "    Port:    $FRONTEND_PORT"
        echo -e "    Log:     $FE_LOG"
    else
        echo -e "    Status:  ${RED}gestoppt${RESET}"
    fi

    echo ""
    echo -e "  ${BOLD}DMS OCR:${RESET}"
    if curl -s "http://localhost:$BACKEND_PORT/api/v1/dms/ocr-status" 2>/dev/null | grep -q '"available":true'; then
        echo -e "    Status:  ${GREEN}verfügbar${RESET}"
    else
        echo -e "    Status:  ${YELLOW}nicht verfügbar (OCR deaktiviert oder nicht installiert)${RESET}"
    fi

    echo ""
    echo -e "  ${BOLD}Projektordner:${RESET} $PROJECT_DIR"
    echo -e "  ${BOLD}Log-Verzeichnis:${RESET} $LOG_DIR"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════
# Interactive Dashboard
# ═══════════════════════════════════════════════════════════════════════

dashboard() {
    log_header "Danwa Dashboard"
    echo ""
    echo -e "  ${CYAN}╔════════════════════════════════════╗${RESET}"
    echo -e "  ${CYAN}║     D A N W A   M A N A G E R     ║${RESET}"
    echo -e "  ${CYAN}╚════════════════════════════════════╝${RESET}"
    echo ""
    echo -e "  ${BOLD}1${RESET}) Backend  ${GREEN}starten${RESET}"
    echo -e "  ${BOLD}2${RESET}) Backend  ${YELLOW}stoppen${RESET}"
    echo -e "  ${BOLD}3${RESET}) Frontend ${GREEN}starten${RESET}"
    echo -e "  ${BOLD}4${RESET}) Frontend ${YELLOW}stoppen${RESET}"
    echo -e "  ${BOLD}5${RESET}) Beides   ${GREEN}starten${RESET}"
    echo -e "  ${BOLD}6${RESET}) Beides   ${YELLOW}stoppen${RESET}"
    echo -e "  ${BOLD}7${RESET}) Status anzeigen"
    echo -e "  ${BOLD}8${RESET}) Backend-Logs live verfolgen"
    echo -e "  ${BOLD}9${RESET}) Frontend-Logs live verfolgen"
    echo -e "  ${BOLD}0${RESET}) Neustart (beides)"
    echo -e "  ${BOLD}q${RESET}) Beenden"
    echo ""
    echo -n "  Auswahl: "
}

# ═══════════════════════════════════════════════════════════════════════
# Documentation
# ═══════════════════════════════════════════════════════════════════════

DOCS_DIR="$PROJECT_DIR/docs"

doc_api() {
    log_step "API-Referenz generieren (OpenAPI → Markdown) …"
    cd "$PROJECT_DIR"
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
    uv run python scripts/export_openapi.py --both 2>&1
    if [[ $? -eq 0 ]]; then
        log_ok "API-Referenz generiert: $DOCS_DIR/api-reference.md"
    else
        log_error "API-Referenz fehlgeschlagen"
        return 1
    fi
}

doc_pdoc() {
    log_step "Python API-Doku generieren (pdoc) …"
    cd "$PROJECT_DIR"
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"

    if ! uv run python -c "import pdoc" 2>/dev/null; then
        log_warn "pdoc nicht installiert — installiere …"
        uv add --dev pdoc 2>&1
    fi

    local output_dir="$DOCS_DIR/api"
    mkdir -p "$output_dir"
    uv run pdoc backend/ -o "$output_dir" --docformat google 2>&1
    if [[ $? -eq 0 ]]; then
        log_ok "pdoc generiert: $output_dir/index.html"
    else
        log_error "pdoc fehlgeschlagen"
        return 1
    fi
}

doc_architecture() {
    log_step "Architektur-Doku generieren (GitNexus Wiki) …"

    # Prüfe Node.js Version
    if ! check_node_version 22; then
        return 1
    fi

    cd "$PROJECT_DIR"

    local output_dir="$DOCS_DIR/architecture"
    mkdir -p "$output_dir"

    if command -v npx &>/dev/null; then
        # Prüfe ob Index existiert
        if ! npx gitnexus status 2>&1 | grep -q "indexed"; then
            log_warn "Index nicht vorhanden — erstelle …"
            npx gitnexus analyze 2>&1
        fi

        # GitNexus Wiki generiert direkt ins Repo-Verzeichnis
        npx gitnexus wiki -f 2>&1
        if [[ $? -eq 0 ]]; then
            # Wiki wird in .gitnexus/wiki/ generiert, kopiere nach docs/architecture/
            if [[ -d ".gitnexus/wiki" ]]; then
                cp -r .gitnexus/wiki/* "$output_dir/" 2>/dev/null || true
                log_ok "GitNexus Wiki generiert: $output_dir/"
            else
                log_warn "Wiki-Verzeichnis nicht gefunden"
                return 1
            fi
        else
            log_error "GitNexus Wiki fehlgeschlagen — LLM API Key erforderlich"
            log_info "Setup: npx gitnexus wiki --provider <provider> --api-key <key>"
            return 1
        fi
    else
        log_error "npx nicht verfügbar — bitte Node.js installieren"
        return 1
    fi
}

doc_update() {
    local mode="${1:-all}"
    local dry_run="${2:-false}"

    log_step "Dokumentation aktualisieren (LLM-basiert) …"

    cd "$PROJECT_DIR"
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"

    local args=""
    case "$mode" in
        tech) args="--tech" ;;
        user) args="--user" ;;
        all|"") args="--all" ;;
    esac

    if [[ "$dry_run" == "true" ]]; then
        args="$args --dry-run"
    fi

    uv run python scripts/doc_update.py $args 2>&1
    if [[ $? -eq 0 ]]; then
        log_ok "Dokumentation aktualisiert"
    else
        log_error "Dokumentation-Update fehlgeschlagen"
        return 1
    fi
}

doc_all() {
    log_header "Alle Dokumentation generieren"
    doc_api
    doc_pdoc
    doc_architecture
    log_ok "Alle Dokumentation generiert"
}

doc_help() {
    log_header "Dokumentation Commands"
    echo ""
    echo "  ./manage.sh doc              Übersicht aller Doc-Commands"
    echo "  ./manage.sh doc-api          OpenAPI → docs/api-reference.md"
    echo "  ./manage.sh doc-pdoc         Python Docstrings → docs/api/"
    echo "  ./manage.sh doc-architecture GitNexus Wiki → docs/architecture/"
    echo "  ./manage.sh doc-update       LLM-basierte Doc-Updates"
    echo "  ./manage.sh doc-update tech  Nur technische Doku"
    echo "  ./manage.sh doc-update user  Nur User Manual"
    echo "  ./manage.sh doc-update --dry-run Vorschau ohne Änderungen"
    echo "  ./manage.sh doc-all          Alle Doc-Generierungen"
    echo "  ./manage.sh adr-new \"Titel\"  Neue ADR erstellen"
    echo "  ./manage.sh adr-check        Prüfen ob ADRs fehlen"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════
# ADR (Architecture Decision Records)
# ═══════════════════════════════════════════════════════════════════════

ADR_DIR="$DOCS_DIR/adr"

adr_new() {
    local title="${1:-}"
    if [[ -z "$title" ]]; then
        log_error "Titel erforderlich: ./manage.sh adr-new \"Titel\""
        return 1
    fi

    mkdir -p "$ADR_DIR"

    # Nächste Nummer finden (nur NNN*-*.md Pattern, mindestens 3 Ziffern gefolgt von Bindestrich und Buchstabe)
    local max_num=0
    for f in "$ADR_DIR"/[0-9]*.md; do
        local bname
        bname="$(basename "$f")"
        if [[ "$bname" =~ ^[0-9]{3,4}-[a-zA-Z] ]]; then
            local num
            num="${bname%%-*}"
            # Remove leading zeros for comparison
            num=$((10#$num))
            if [[ "$num" -gt "$max_num" ]]; then
                max_num="$num"
            fi
        fi
    done
    local next_num=$(( max_num + 1 ))
    local padded
    padded="$(printf "%03d" "$next_num")"
    local filename="$ADR_DIR/${padded}-${title// /-}.md"

    # Prüfen ob Datei bereits existiert
    if [[ -f "$filename" ]]; then
        log_error "ADR existiert bereits: $filename"
        return 1
    fi

    cat > "$filename" << EOF
# ADR-${padded}: ${title}

**Status:** Proposed
**Date:** $(date -I)
**Context:** Was war das Problem?

<!-- Beschreibe den Hintergrund und das Problem, das diese Entscheidung erfordert hat -->

**Decision:** Was wurde entschieden?

<!-- Beschreibe die getroffene Entscheidung -->

**Consequences:** Was sind die Folgen?

<!-- Beschreibe die positiven und negativen Konsequenzen -->

**Affected Files:**

<!-- Liste der betroffenen Dateien -->

**Alternatives Considered:**

<!-- Welche Alternativen wurden geprüft und warum verworfen? -->
EOF

    log_ok "ADR erstellt: $filename"
}

adr_check() {
    log_step "Prüfe fehlende ADRs …"

    # Definiere Kern-Verzeichnisse die Architektur-Änderungen darstellen
    local core_dirs=(
        "backend/api/routers"
        "backend/services"
        "backend/blueprints"
        "backend/modules"
        "backend/models"
        "backend/config"
    )

    local last_adr_check="$DOCS_DIR/.last-adr-check"
    local since="HEAD~20"
    if [[ -f "$last_adr_check" ]]; then
        since="$(cat "$last_adr_check")"
    fi

    local changes_found=false
    for dir in "${core_dirs[@]}"; do
        local changed
        changed="$(git diff "$since" --name-only -- "${dir}/*.py" 2>/dev/null)" || true
        if [[ -n "$changed" ]]; then
            changes_found=true
            log_warn "Architektur-Änderungen in: $dir"
            echo "$changed" | while read -r f; do
                echo "  - $f"
            done
        fi
    done

    if [[ "$changes_found" == "false" ]]; then
        log_ok "Keine Architektur-Änderungen seit letztem Check"
    else
        log_warn "Prüfe ob neue ADRs für diese Änderungen erforderlich sind …"
        log_info "Erstelle bei Bedarf eine neue ADR: ./manage.sh adr-new \"Titel\""
    fi

    date -Iseconds > "$last_adr_check"
}

# ═══════════════════════════════════════════════════════════════════════
# Clean
# ═══════════════════════════════════════════════════════════════════════

clean_caches() {
    log_step "Caches aufräumen …"
    find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null || true
    find "$FE_DIR/node_modules/.cache" -maxdepth 1 -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_DIR" -type d -name "*.pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    log_ok "Caches gelöscht"
}

# ═══════════════════════════════════════════════════════════════════════
# Hauptlogik
# ═══════════════════════════════════════════════════════════════════════

cmd="${1:-}"

case "$cmd" in
    start)
        what="${2:-all}"
        case "$what" in
            be|backend) start_backend ;;
            fe|frontend) start_frontend ;;
            all|"") start_backend && start_frontend ;;
        esac
        ;;
    stop)
        what="${2:-all}"
        case "$what" in
            be|backend) stop_backend ;;
            fe|frontend) stop_frontend ;;
            all|"") stop_backend && stop_frontend ;;
        esac
        ;;
    restart|reload)
        stop_backend
        stop_frontend
        sleep 1
        # Python-Bytecode-Caches löschen — sonst lädt der neue Prozess alte .pyc-Dateien
        find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null || true
        start_backend
        start_frontend
        ;;
    status|st)
        show_status
        ;;
    logs)
        show_logs "${2:-all}"
        ;;
    dashboard|dash|d)
        while true; do
            dashboard
            read -r choice
            case "$choice" in
                1) start_backend ;;
                2) stop_backend ;;
                3) start_frontend ;;
                4) stop_frontend ;;
                5) start_backend && start_frontend ;;
                6) stop_backend && stop_frontend ;;
                7) show_status ;;
                8) show_logs be ;;
                9) show_logs fe ;;
                0)
                    stop_backend && stop_frontend
                    sleep 1
                    start_backend && start_frontend
                    ;;
                q|Q|quit|exit) log_info "Bye!"; exit 0 ;;
                *) log_warn "Ungültige Auswahl: $choice" ;;
            esac
            echo ""
            echo -n "  Enter drücken …"
            read -r
            clear
        done
        ;;
    clean)
        clean_caches
        ;;
    doc)
        doc_help
        ;;
    doc-api)
        doc_api
        ;;
    doc-pdoc)
        doc_pdoc
        ;;
    doc-architecture)
        doc_architecture
        ;;
    doc-update)
        mode="${2:-all}"
        dry="false"
        if [[ "$mode" == "--dry-run" ]]; then
            dry="true"
            mode="all"
        fi
        doc_update "$mode" "$dry"
        ;;
    doc-all)
        doc_all
        ;;
    adr-new)
        adr_new "${2:-}"
        ;;
    adr-check)
        adr_check
        ;;
    test)
        log_step "Tests ausführen …"
        cd "$PROJECT_DIR"
        export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
        export UV_PYTHONPATH="${PROJECT_DIR}:${UV_PYTHONPATH:-}"
        uv run pytest tests/backend/test_dms_ocr.py tests/backend/test_dms_api.py tests/test_paddleocr_integration.py tests/test_dms_document_processor.py -v 2>&1
        ;;
    help|--help|-h)
        echo "Danwa Manager"
        echo ""
        echo "  ./manage.sh              interaktives Dashboard"
        echo "  ./manage.sh start        Backend + Frontend starten"
        echo "  ./manage.sh start be     nur Backend starten"
        echo "  ./manage.sh start fe     nur Frontend starten"
        echo "  ./manage.sh stop         alles stoppen"
        echo "  ./manage.sh restart      alles neu starten"
        echo "  ./manage.sh status       Status anzeigen"
        echo "  ./manage.sh logs         Live-Logs (beide)"
        echo "  ./manage.sh logs be      Backend-Logs"
        echo "  ./manage.sh logs fe      Frontend-Logs"
        echo "  ./manage.sh clean        Caches aufräumen"
        echo "  ./manage.sh test         Tests ausführen"
        echo "  ./manage.sh doc          Dokumentation Commands"
        echo "  ./manage.sh doc-api      OpenAPI → Markdown"
        echo "  ./manage.sh doc-pdoc     Docstrings → HTML"
        echo "  ./manage.sh doc-architecture  GitNexus Wiki"
        echo "  ./manage.sh doc-update   LLM-basierte Updates"
        echo "  ./manage.sh doc-all      Alle Docs generieren"
        echo "  ./manage.sh adr-new      Neue ADR erstellen"
        echo "  ./manage.sh adr-check    ADR-Check"
        ;;
    *)
        log_error "Unbekannter Befehl: '$cmd'. Versuche: ./manage.sh help"
        exit 1
        ;;
esac