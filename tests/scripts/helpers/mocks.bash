# tests/scripts/helpers/mocks.bash
#
# Mock helpers for bats tests. NEVER start real uvicorn / npm / production
# services in tests — these mocks provide equivalent surfaces for unit tests.
#
# Conventions:
#   - All mocks use TEST_TMP for their artifacts
#   - Mocks register a trap for teardown cleanup
#   - MOCK_PID is exported for teardown() to kill them

# mock_uvicorn — creates a script that mimics uvicorn's pid + log behavior
# Usage: mock_uvicorn [sleep_seconds=30]
mock_uvicorn() {
    local sleep_s="${1:-30}"
    local script="$TEST_TMP/mock-uvicorn.sh"
    cat > "$script" <<EOF
#!/usr/bin/env bash
# Mock uvicorn — just sleeps so PID is alive
sleep $sleep_s
EOF
    chmod +x "$script"
    echo "$script"
}

# start_mock_process — spawns a background process and writes its PID
# Usage: start_mock_process <pid_file> <command...>
start_mock_process() {
    local pid_file="$1"
    shift
    "$@" &
    local pid=$!
    echo "$pid" > "$pid_file"
    echo "$pid"
}

# start_mock_http_server — python http server on a given port for wait_for_url tests
# Usage: start_mock_http_server [port=0]
start_mock_http_server() {
    local port="${1:-0}"
    python3 -c "
import http.server, socketserver, sys, time, os
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')
    def log_message(self, *args):
        pass

socketserver.TCPServer.allow_reuse_address = True
port = int(os.environ.get('MOCK_PORT', '$port'))
with socketserver.TCPServer(('127.0.0.1', port), Handler) as s:
    s.serve_forever()
" &
    MOCK_PID=$!
    sleep 0.3
}

# kill_mock_process — clean up a mock started above
kill_mock_process() {
    local pid="${1:-${MOCK_PID:-}}"
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
}