#!/bin/bash
# =============================================================================
# Chainlit-Migration Cleanup Script
# Idempotent — safe to run multiple times. Reports what was done.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1

echo "🧹 Chainlit-Cleanup gestartet …"
CHANGES=0

# ---------------------------------------------------------------------------
# 1. Chainlit aus pyproject.toml entfernen (falls noch vorhanden)
# ---------------------------------------------------------------------------
if grep -qi "chainlit" pyproject.toml 2>/dev/null; then
    echo "  ⚠️  Chainlit-Referenz in pyproject.toml gefunden — bitte manuell prüfen:"
    grep -ni "chainlit" pyproject.toml
    echo "  → Entferne die Zeile(n) manuell und führe 'uv sync' aus."
    CHANGES=$((CHANGES + 1))
else
    echo "  ✅ pyproject.toml: keine Chainlit-Referenz"
fi

# ---------------------------------------------------------------------------
# 2. .chainlit/-Verzeichnis löschen
# ---------------------------------------------------------------------------
if [ -d ".chainlit" ]; then
    rm -rf .chainlit
    echo "  🗑️  .chainlit/ Verzeichnis gelöscht"
    CHANGES=$((CHANGES + 1))
else
    echo "  ✅ .chainlit/ existiert nicht (bereits entfernt)"
fi

# ---------------------------------------------------------------------------
# 3. Chainlit-Tabellen aus SQLite-Datenbanken droppen
# ---------------------------------------------------------------------------
DBS=("memory/debates.db" "memory/dms.db" "data/audit.db")
CHAINLIT_TABLES=("chainlit_element" "chainlit_step" "chainlit_user" "chainlit_user_env")

for db in "${DBS[@]}"; do
    if [ ! -f "$db" ]; then
        continue
    fi
    for table in "${CHAINLIT_TABLES[@]}"; do
        EXISTS=$(python3 -c "
import sqlite3
conn = sqlite3.connect('$db')
r = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='$table'\").fetchone()
print('yes' if r else 'no')
conn.close()
" 2>/dev/null || echo "no")
        if [ "$EXISTS" = "yes" ]; then
            python3 -c "
import sqlite3
conn = sqlite3.connect('$db')
conn.execute('DROP TABLE IF EXISTS $table')
conn.commit()
conn.close()
"
            echo "  🗑️  $db: Tabelle '$table' gelöscht"
            CHANGES=$((CHANGES + 1))
        fi
    done
done
echo "  ✅ SQLite-Datenbanken: keine Chainlit-Tabellen gefunden"

# ---------------------------------------------------------------------------
# 4. Alte Chainlit-Dateien nach archive/ verschieben (sofern noch vorhanden)
# ---------------------------------------------------------------------------
CHAINLIT_FILES=(
    "src/ui/chainlit_app.py"
    "src/ui/chainlit_app.py_v1"
    "src/ui/dashboard.py"
    "src/ui/dms_dashboard.py"
    "chainlit.md"
)

for f in "${CHAINLIT_FILES[@]}"; do
    if [ -f "$f" ]; then
        mkdir -p archive/chainlit
        mv "$f" "archive/chainlit/$(basename "$f")"
        echo "  📦 $f → archive/chainlit/"
        CHANGES=$((CHANGES + 1))
    fi
done

# ---------------------------------------------------------------------------
# 5. Chainlit-Tests archivieren (sofern noch vorhanden)
# ---------------------------------------------------------------------------
CHAINLIT_TESTS=(
    "tests/test_chainlit_app.py"
    "tests/test_dms_dashboard.py"
    "tests/test_debate_engine_rag.py"
    "tests/test_dms_integration.py"
)

for f in "${CHAINLIT_TESTS[@]}"; do
    if [ -f "$f" ]; then
        mkdir -p archive/chainlit/tests
        mv "$f" "archive/chainlit/tests/$(basename "$f")"
        echo "  📦 $f → archive/chainlit/tests/"
        CHANGES=$((CHANGES + 1))
    fi
done

# ---------------------------------------------------------------------------
# 6. src/ui/__init__.py bereinigen (Chainlit-Imports entfernen)
# ---------------------------------------------------------------------------
if [ -f "src/ui/__init__.py" ]; then
    if grep -qE "^(from|import).*chainlit|^(from|import).*dms_dashboard|^(from|import).*dashboard" src/ui/__init__.py 2>/dev/null; then
        # Leere __init__.py ersetzen
        echo '# src/ui — UI module (migrated to frontend/)' > src/ui/__init__.py
        echo "  🔧 src/ui/__init__.py: Chainlit-Imports entfernt"
        CHANGES=$((CHANGES + 1))
    else
        echo "  ✅ src/ui/__init__.py: keine Chainlit-Imports"
    fi
fi

# ---------------------------------------------------------------------------
# Zusammenfassung
# ---------------------------------------------------------------------------
echo ""
if [ "$CHANGES" -eq 0 ]; then
    echo "✅ Keine Chainlit-Reste gefunden — System ist sauber."
else
    echo "🧹 Cleanup abgeschlossen: $CHANGES Aktion(en) ausgeführt."
fi
