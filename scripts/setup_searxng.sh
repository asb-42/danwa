#!/usr/bin/env bash
set -e
SEARX_DIR="$HOME/.local/share/searxng"
mkdir -p "$SEARX_DIR"

echo "📦 Installiere SearXNG (native)..."
python3 -m venv "$SEARX_DIR/.venv"
source "$SEARX_DIR/.venv/bin/activate"
pip install "searxng[gunicorn]"

echo "📜 Erstelle Privacy-Config..."
cat > "$SEARX_DIR/settings.yml" <<EOF
use_default_settings: true
server:
  bind_address: "127.0.0.1"
  port: 8080
  secret_key: "$(openssl rand -hex 32)"
  limiter: false
  image_proxy: false
search:
  formats: [json, html]
  safe_search: 1
  default_lang: "de-de"
engines:
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
    disabled: false
  - name: startpage
    engine: startpage
    shortcut: sp
    disabled: false
  - name: qwant
    engine: qwant
    shortcut: qw
    disabled: false
outgoing:
  request_timeout: 6.0
  max_request_timeout: 10.0
  pool_connections: 50
  pool_maxsize: 10
  enable_http2: false
ui:
  static_use_hash: true
  default_locale: "de"
  theme: simple
  default_theme: simple
general:
  debug: false
  instance_name: "Local Privacy Search"
  privacypolicy_url: ""
  contact_url: ""
enable_metrics: false
EOF

mkdir -p "$SEARX_DIR/pids" "$SEARX_DIR/logs"
nohup $SEARX_DIR/.venv/bin/gunicorn -b 127.0.0.1:8080 -w 2 --timeout 30 searx.webapp > "$SEARX_DIR/logs/searxng.log" 2>&1 &
echo $! > "$SEARX_DIR/pids/searxng.pid"
echo "✅ SearXNG läuft: http://127.0.0.1:8080"
echo "🔍 JSON-API-Test: curl 'http://127.0.0.1:8080/search?q=test&format=json'"
echo "📝 Logs: $SEARX_DIR/logs/searxng.log"
echo "🛑 Stop: kill \$(cat $SEARX_DIR/pids/searxng.pid)"