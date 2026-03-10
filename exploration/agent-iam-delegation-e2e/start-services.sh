#!/bin/bash
# =============================================================================
# start-services.sh — iTerm2 Split Pane Launcher
#
# Opens 3 vertical panes in iTerm2 (or 3 Terminal.app windows as fallback),
# each running one service with live logs visible.
#
# Usage: bash start-services.sh
# =============================================================================

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

SPINNER_CHARS='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

spinner() {
    local pid=$1
    local msg="${2:-Working...}"
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        local ch="${SPINNER_CHARS:$((i % ${#SPINNER_CHARS})):1}"
        printf "\r  ${CYAN}%s${NC} %s" "$ch" "$msg"
        i=$((i + 1))
        sleep 0.1
    done
    printf "\r"
}

wait_for_health() {
    local url=$1
    local name=$2
    local max_attempts=60
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 0.5
    done
    return 1
}

# =============================================================================
# Detect terminal emulator
# =============================================================================

use_iterm2=false
if [ "$(uname)" = "Darwin" ]; then
    if osascript -e 'id of application "iTerm2"' > /dev/null 2>&1; then
        use_iterm2=true
    fi
fi

echo ""
echo -e "${BOLD}┌──────────────────────────────────────────────────────┐${NC}"
echo -e "${BOLD}│        Service Launcher — 3 Panes / 3 Services      │${NC}"
echo -e "${BOLD}└──────────────────────────────────────────────────────┘${NC}"
echo ""

# Kill any existing services on ports 8000-8002
EXISTING_PIDS=$(lsof -ti:8000,8001,8002 2>/dev/null || true)
if [ -n "$EXISTING_PIDS" ]; then
    echo -e "  ${YELLOW}▸${NC} Killing existing processes on ports 8000-8002..."
    echo "$EXISTING_PIDS" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

if $use_iterm2; then
    echo -e "  ${GREEN}▸${NC} iTerm2 detected — launching split panes"
    echo ""

    osascript - "$DIR" <<'APPLESCRIPT_END'
on run argv
    set projectDir to item 1 of argv
    set cmd1 to "cd " & quoted form of projectDir & " && echo '=== GLChat BE (port 8000) ===' && uv run python glchat_be.py"
    set cmd2 to "cd " & quoted form of projectDir & " && echo '=== AIP Backend (port 8001) ===' && uv run python aip_backend.py"
    set cmd3 to "cd " & quoted form of projectDir & " && echo '=== GL Connectors (port 8002) ===' && uv run python connectors.py"

    tell application "iTerm2"
        activate
        set newWindow to (create window with default profile)

        tell newWindow
            tell current session of current tab
                set name to "GLChat BE :8000"
                write text cmd1
                set s2 to (split horizontally with default profile)
            end tell
            tell s2
                set name to "AIP Backend :8001"
                write text cmd2
                set s3 to (split horizontally with default profile)
            end tell
            tell s3
                set name to "Connectors :8002"
                write text cmd3
            end tell
        end tell
    end tell
end run
APPLESCRIPT_END

else
    echo -e "  ${YELLOW}▸${NC} iTerm2 not found — using Terminal.app (3 windows)"
    echo ""

    osascript - "$DIR" <<'APPLESCRIPT_END'
on run argv
    set projectDir to item 1 of argv

    tell application "Terminal"
        activate

        do script "cd " & quoted form of projectDir & " && echo '=== GLChat BE (port 8000) ===' && uv run python glchat_be.py"
        set custom title of front window to "GLChat BE :8000"

        do script "cd " & quoted form of projectDir & " && echo '=== AIP Backend (port 8001) ===' && uv run python aip_backend.py"
        set custom title of front window to "AIP Backend :8001"

        do script "cd " & quoted form of projectDir & " && echo '=== GL Connectors (port 8002) ===' && uv run python connectors.py"
        set custom title of front window to "Connectors :8002"
    end tell
end run
APPLESCRIPT_END

fi

# =============================================================================
# Wait for all services to be healthy
# =============================================================================

# Wait for all 3 services to be healthy
# Services run in iTerm2 panes and may need time to compile via uv
MAX_WAIT=90
ELAPSED=0
ok_8000=0; ok_8001=0; ok_8002=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    [ "$ok_8000" = "0" ] && curl -sf http://localhost:8000/health > /dev/null 2>&1 && ok_8000=1
    [ "$ok_8001" = "0" ] && curl -sf http://localhost:8001/health > /dev/null 2>&1 && ok_8001=1
    [ "$ok_8002" = "0" ] && curl -sf http://localhost:8002/health > /dev/null 2>&1 && ok_8002=1

    if [ "$ok_8000" = "1" ] && [ "$ok_8001" = "1" ] && [ "$ok_8002" = "1" ]; then
        break
    fi

    # Show progress with spinner
    local_ch="${SPINNER_CHARS:$((ELAPSED % ${#SPINNER_CHARS})):1}"
    printf "\r  ${CYAN}%s${NC} Waiting for services... (%ss)" "$local_ch" "$ELAPSED"
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done
printf "\r\033[K"

[ "$ok_8000" = "1" ] \
    && echo -e "  ${GREEN}✓${NC} GLChat BE       ${DIM}http://localhost:8000${NC}" \
    || echo -e "  ${RED}✗${NC} GLChat BE       ${DIM}http://localhost:8000${NC}"
[ "$ok_8001" = "1" ] \
    && echo -e "  ${GREEN}✓${NC} AIP Backend     ${DIM}http://localhost:8001${NC}" \
    || echo -e "  ${RED}✗${NC} AIP Backend     ${DIM}http://localhost:8001${NC}"
[ "$ok_8002" = "1" ] \
    && echo -e "  ${GREEN}✓${NC} GL Connectors   ${DIM}http://localhost:8002${NC}" \
    || echo -e "  ${RED}✗${NC} GL Connectors   ${DIM}http://localhost:8002${NC}"
echo ""

if [ "$ok_8000" = "1" ] && [ "$ok_8001" = "1" ] && [ "$ok_8002" = "1" ]; then
    echo -e "  ${BOLD}All services healthy.${NC} Run ${CYAN}make demo${NC} to start the interactive demo."
    echo ""
else
    echo -e "  ${RED}Some services failed to start.${NC} Check the service panes for error logs."
    echo ""
    exit 1
fi
