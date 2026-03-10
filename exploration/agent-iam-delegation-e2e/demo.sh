#!/bin/bash
# =============================================================================
# Agent IAM Delegation E2E — Interactive Demo
#
# Phase 1: Auto-setup (register users, login, register agent)
# Phase 2: Interactive menu for scenario selection
#
# Prerequisites:
#   - PostgreSQL running on localhost:5432
#   - All 3 services running (use: make start-services)
# =============================================================================

set -e

BASE_URL="http://localhost:8000"

# =============================================================================
# Colors & Formatting
# =============================================================================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
UNDERLINE='\033[4m'
NC='\033[0m'

SPINNER_CHARS='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

# =============================================================================
# UX Helper Functions
# =============================================================================

spinner() {
    local pid=$1
    local msg="${2:-Working...}"
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        local ch="${SPINNER_CHARS:$((i % ${#SPINNER_CHARS})):1}"
        printf "\r  ${CYAN}%s${NC} %s" "$ch" "$msg"
        i=$((i + 1))
        sleep 0.08
    done
    printf "\r\033[K"
}

countdown() {
    local msg="${1:-Executing in}"
    for i in 3 2 1; do
        printf "\r  ${DIM}%s %s...${NC}" "$msg" "$i"
        sleep 0.6
    done
    printf "\r\033[K"
}

pp() {
    if command -v jq &> /dev/null; then
        jq '.'
    else
        cat
    fi
}

section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${BOLD}${CYAN}$1${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

success() {
    echo -e "  ${GREEN}✓${NC} $1"
}

fail() {
    echo -e "  ${RED}✗${NC} $1"
}

info() {
    echo -e "  ${DIM}$1${NC}"
}

# Pretty-print user info box
user_box() {
    local name=$1 role=$2 email=$3
    local role_color=$GREEN
    [ "$role" = "member" ] && role_color=$YELLOW
    [ "$role" = "viewer" ] && role_color=$MAGENTA

    echo ""
    echo -e "  ${BOLD}── User ────────────────────────────────${NC}"
    echo -e "    Name:  ${BOLD}$name${NC}"
    echo -e "    Role:  ${role_color}${BOLD}$role${NC}"
    echo -e "    Email: ${DIM}$email${NC}"
    echo ""
}

# 4-column scope attenuation table: User → Agent → Worker → Tool
scope_table() {
    local response_json=$1

    local user_scopes_json=$(echo "$response_json" | jq -r '.user.scopes // .abac.user_scopes // []' 2>/dev/null)
    local agent_ceiling_json=$(echo "$response_json" | jq -r '.abac.agent_ceiling // []' 2>/dev/null)

    # Parse scope arrays from JSON
    local user_scopes=$(echo "$user_scopes_json" | jq -r '.[]' 2>/dev/null)
    local agent_scopes=$(echo "$agent_ceiling_json" | jq -r '.[]' 2>/dev/null)

    # Collect worker and tool scopes from delegation_chain
    local worker_scopes=$(echo "$response_json" | jq -r '.aip_response.delegation_chain[]? | select(.depth == 3) | .scopes[]?' 2>/dev/null | sort -u)
    local tool_scopes=$(echo "$response_json" | jq -r '.aip_response.delegation_chain[]? | select(.depth == 4) | .scope // empty' 2>/dev/null | sort -u)

    # All possible scopes in the demo
    local all_scopes=("calendar:read" "calendar:write" "slack:post" "notion:read" "gmail:send")

    echo ""
    echo -e "  ${BOLD}── Scope Attenuation (4 levels) ──────────────────────${NC}"
    echo ""
    echo -e "    Scope              User  Agent  Worker  Tool"
    echo -e "    ────────────────   ────  ─────  ──────  ────"

    for scope in "${all_scopes[@]}"; do
        local in_user="·"
        local in_agent="·"
        local in_worker="·"
        local in_tool="·"

        if echo "$user_scopes" | grep -q "^${scope}$" 2>/dev/null; then
            in_user="✓"
        fi

        if echo "$agent_scopes" | grep -q "^${scope}$" 2>/dev/null; then
            in_agent="✓"
        fi

        if echo "$worker_scopes" | grep -q "^${scope}$" 2>/dev/null; then
            in_worker="✓"
        fi

        if echo "$tool_scopes" | grep -q "^${scope}$" 2>/dev/null; then
            in_tool="✓"
        fi

        local c_user="${DIM}${in_user}${NC}"; [ "$in_user" = "✓" ] && c_user="${GREEN}✓${NC}"
        local c_agent="${DIM}${in_agent}${NC}"; [ "$in_agent" = "✓" ] && c_agent="${GREEN}✓${NC}"
        local c_worker="${DIM}${in_worker}${NC}"; [ "$in_worker" = "✓" ] && c_worker="${GREEN}✓${NC}"
        local c_tool="${DIM}${in_tool}${NC}"; [ "$in_tool" = "✓" ] && c_tool="${GREEN}✓${NC}"

        echo -e "    $(printf '%-18s' "$scope")    ${c_user}     ${c_agent}      ${c_worker}       ${c_tool}"
    done
    echo ""
}

# Execution results display — shows orchestrator, workers, and tools
execution_results() {
    local response_json=$1
    local log=$(echo "$response_json" | jq -r '.aip_response.execution_log // []' 2>/dev/null)

    if [ -z "$log" ] || [ "$log" = "null" ] || [ "$log" = "[]" ]; then
        return
    fi

    echo ""
    echo -e "  ${BOLD}── Execution Results ───────────────────────────────${NC}"
    echo ""

    echo "$log" | jq -c '.[]' 2>/dev/null | while read -r entry; do
        local step=$(echo "$entry" | jq -r '.step')
        local status=$(echo "$entry" | jq -r '.status')
        local depth=$(echo "$step" | cut -d: -f1)
        local label=$(echo "$step" | cut -d: -f2)

        local icon="${YELLOW}⊘${NC}"
        if [ "$status" = "validated" ] || [ "$status" = "delegated" ] || [ "$status" = "executed" ]; then
            icon="${GREEN}✓${NC}"
        elif [ "$status" = "delegation_failed" ] || [ "$status" = "denied" ]; then
            icon="${RED}✗${NC}"
        fi

        if [ "$depth" = "d2" ]; then
            local scopes=$(echo "$entry" | jq -r '.scopes | join(", ")' 2>/dev/null)
            local planned=$(echo "$entry" | jq -r '.planned_tools | join(", ")' 2>/dev/null)
            echo -e "    ${icon}  ${BOLD}${depth} Orchestrator${NC}   ${DIM}${status}${NC}"
            echo -e "       ${DIM}scopes:  ${scopes}${NC}"
            echo -e "       ${DIM}planned: ${planned}${NC}"
        elif [ "$depth" = "d3" ]; then
            local scopes=$(echo "$entry" | jq -r '.scopes // [] | join(", ")' 2>/dev/null)
            local tools=$(echo "$entry" | jq -r '.tools // [] | join(", ")' 2>/dev/null)
            echo -e "    ${icon}  ${BOLD}${depth} Worker${NC}         ${label}  ${DIM}${status}${NC}"
            if [ -n "$scopes" ]; then
                echo -e "       ${DIM}scopes:  ${scopes}${NC}"
            fi
            if [ -n "$tools" ]; then
                echo -e "       ${DIM}tools:   ${tools}${NC}"
            fi
            local error=$(echo "$entry" | jq -r '.error // empty' 2>/dev/null)
            if [ -n "$error" ]; then
                echo -e "       ${RED}error:   ${error}${NC}"
            fi
        elif [ "$depth" = "d4" ]; then
            local scope=$(echo "$entry" | jq -r '.scope // empty' 2>/dev/null)
            local worker=$(echo "$entry" | jq -r '.worker // empty' 2>/dev/null)
            echo -e "    ${icon}  ${BOLD}${depth} Tool${NC}           $(printf '%-22s' "$label")  ${DIM}${status}${NC}"
            local error=$(echo "$entry" | jq -r '.error // empty' 2>/dev/null)
            if [ -n "$error" ]; then
                echo -e "       ${RED}error:   ${error}${NC}"
            fi
        fi
    done
    echo ""
}

# Show delegation chain (4 levels)
show_token() {
    local response_json=$1
    local user_bearer_token=$2
    local ref=$(echo "$response_json" | jq -r '.delegation_ref // empty' 2>/dev/null)

    if [ -z "$ref" ]; then
        return
    fi

    # Extract user info
    local user_email=$(echo "$response_json" | jq -r '.user.email // empty' 2>/dev/null)
    local user_role=$(echo "$response_json" | jq -r '.user.role // empty' 2>/dev/null)
    local user_scopes=$(echo "$response_json" | jq -r '.user.scopes // [] | join(", ")' 2>/dev/null)
    echo ""
    echo -e "  ${BOLD}── Delegation Chain (4 levels) ──────────────────────────────────────${NC}"
    echo ""
    echo -e "  ${BOLD}d1${NC}  ${CYAN}User${NC}           ${user_email} (${user_role})"
    echo -e "      ${DIM}scopes:        ${user_scopes}${NC}"
    echo -e "      ${DIM}token:         ${user_bearer_token}${NC}"

    # Parse delegation_chain from AIP response
    local chain=$(echo "$response_json" | jq -r '.aip_response.delegation_chain // []' 2>/dev/null)

    if [ -n "$chain" ] && [ "$chain" != "null" ] && [ "$chain" != "[]" ]; then
        echo "$chain" | jq -c '.[]' 2>/dev/null | while read -r entry; do
            local depth=$(echo "$entry" | jq -r '.depth')
            local label=$(echo "$entry" | jq -r '.label')
            local entry_token=$(echo "$entry" | jq -r '.token')

            if [ "$depth" = "2" ]; then
                local scopes=$(echo "$entry" | jq -r '.scopes | join(", ")' 2>/dev/null)
                echo ""
                echo -e "  ${BOLD}d2${NC}  ${CYAN}Orchestrator${NC}   ${label}"
                echo -e "      ${DIM}scopes:        ${scopes}${NC}"
                echo -e "      ${DIM}token:         ${entry_token}${NC}"
            elif [ "$depth" = "3" ]; then
                local scopes=$(echo "$entry" | jq -r '.scopes | join(", ")' 2>/dev/null)
                echo ""
                echo -e "  ${BOLD}d3${NC}  ${YELLOW}Worker${NC}         ${label}"
                echo -e "      ${DIM}scopes:        ${scopes}${NC}"
                echo -e "      ${DIM}token:         ${entry_token}${NC}"
            elif [ "$depth" = "4" ]; then
                local scope=$(echo "$entry" | jq -r '.scope // empty')
                local worker=$(echo "$entry" | jq -r '.worker // empty')
                echo ""
                echo -e "  ${BOLD}d4${NC}  ${MAGENTA}Tool${NC}           ${label}"
                echo -e "      ${DIM}scope:         ${scope}${NC}"
                echo -e "      ${DIM}worker:        ${worker}${NC}"
                echo -e "      ${DIM}token:         ${entry_token}${NC}"
            fi
        done
    fi

    echo ""
    echo -e "  ${DIM}delegation_ref: ${NC}${BOLD}$ref${NC}"
}

# =============================================================================
# Run a scenario (shared logic)
# =============================================================================
run_scenario() {
    local token=$1
    local name=$2
    local role=$3
    local email=$4
    local message=$5
    local tool_inputs=$6
    local expected=$7

    user_box "$name" "$role" "$email"

    echo ""
    echo -e "  ${BOLD}Message:${NC} ${DIM}\"$message\"${NC}"
    if [ -n "$expected" ]; then
        echo -e "  ${BOLD}Expected:${NC} $expected"
    fi

    countdown

    # Build request body
    local body
    if [ -n "$tool_inputs" ] && [ "$tool_inputs" != "{}" ]; then
        body=$(jq -n \
            --arg agent_id "$AGENT_ID" \
            --arg msg "$message" \
            --argjson tools "$tool_inputs" \
            '{agent_id: $agent_id, user_message: $msg, tool_inputs: $tools}')
    else
        body=$(jq -n \
            --arg agent_id "$AGENT_ID" \
            --arg msg "$message" \
            '{agent_id: $agent_id, user_message: $msg}')
    fi

    # Execute with spinner
    local tmpfile=$(mktemp)
    (curl -s -X POST "$BASE_URL/chat/run-agent" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "$body" > "$tmpfile" 2>&1) &
    local curl_pid=$!
    spinner $curl_pid "Calling /chat/run-agent..."
    wait $curl_pid || true

    local RESPONSE=$(cat "$tmpfile")
    rm -f "$tmpfile"

    # Check for errors
    local error=$(echo "$RESPONSE" | jq -r '.detail // empty' 2>/dev/null)
    if [ -n "$error" ]; then
        fail "Error: $error"
        return
    fi

    # Extract data
    local rule=$(echo "$RESPONSE" | jq -r '.abac.rule // empty' 2>/dev/null)

    # Display results
    echo -e "  ${BOLD}ABAC Rule:${NC} ${DIM}$rule${NC}"
    scope_table "$RESPONSE"
    execution_results "$RESPONSE"
    show_token "$RESPONSE" "$token"

    echo ""
}

# =============================================================================
# Scenario definitions
# =============================================================================
scenario_alice() {
    section "SCENARIO 1: Alice (admin) -> scheduling-agent"
    echo -e "  ${DIM}Admin gets full agent scopes — all tools available${NC}"
    run_scenario "$ALICE_TOKEN" "Alice" "admin" "alice@example.com" \
        "Schedule a meeting and notify the team" \
        '{"calendar.create_event": {"title": "Team Sync", "time": "2026-03-12T15:00:00Z"}, "slack.post_message": {"channel": "#team", "text": "Meeting scheduled!"}}' \
        "ALL 4 agent scopes pass through"
    success "Alice (admin): full delegation complete"
}

scenario_bob() {
    section "SCENARIO 2: Bob (member) -> scheduling-agent"
    echo -e "  ${DIM}Member gets intersection of member scopes and agent scopes${NC}"
    run_scenario "$BOB_TOKEN" "Bob" "member" "bob@example.com" \
        "Schedule a meeting and notify the team" \
        '{"calendar.create_event": {"title": "Bobs Meeting", "time": "2026-03-12T16:00:00Z"}, "slack.post_message": {"channel": "#team", "text": "Bobs meeting!"}}' \
        "calendar:read, calendar:write, notion:read (NO slack:post)"
    success "Bob (member): reduced delegation — slack:post denied"
}

scenario_carol() {
    section "SCENARIO 3: Carol (viewer) -> scheduling-agent"
    echo -e "  ${DIM}Viewer gets read-only scopes only${NC}"
    run_scenario "$CAROL_TOKEN" "Carol" "viewer" "carol@example.com" \
        "Show me my calendar and documents" \
        '{}' \
        "calendar:read, notion:read ONLY (no write, no slack)"
    success "Carol (viewer): read-only delegation complete"
}

scenario_denial() {
    section "SCENARIO 4: Scope denial — gmail:send (not in agent ceiling)"
    echo -e "  ${DIM}Even admin cannot use gmail:send — it's not in agent's allowed_scopes${NC}"
    run_scenario "$ALICE_TOKEN" "Alice" "admin" "alice@example.com" \
        "Send an email to the team via gmail" \
        '{}' \
        "gmail:send BLOCKED — not in agent's allowed_scopes ceiling"

    echo -e "  ${YELLOW}Note:${NC} gmail:send is not in attenuated_scopes because it's not in"
    echo -e "  the agent's allowed_scopes ceiling. The AIP backend won't even plan"
    echo -e "  to call it because the scope is missing from effective_scopes."
    echo ""
    success "Scope ceiling enforcement: gmail:send blocked at delegation creation"
}

scenario_custom() {
    section "SCENARIO 5: Custom — pick a user and type a message"

    echo ""
    echo -e "  ${BOLD}Pick a user:${NC}"
    echo -e "    ${CYAN}[a]${NC} Alice (admin)"
    echo -e "    ${CYAN}[b]${NC} Bob (member)"
    echo -e "    ${CYAN}[c]${NC} Carol (viewer)"
    echo ""
    printf "  Choice: "
    read -r user_choice

    local token name role email
    case "$user_choice" in
        a|A) token=$ALICE_TOKEN; name="Alice"; role="admin"; email="alice@example.com" ;;
        b|B) token=$BOB_TOKEN;   name="Bob";   role="member"; email="bob@example.com" ;;
        c|C) token=$CAROL_TOKEN; name="Carol"; role="viewer"; email="carol@example.com" ;;
        *)   fail "Invalid choice"; return ;;
    esac

    echo ""
    printf "  ${BOLD}Enter message for the agent:${NC} "
    read -r user_message

    if [ -z "$user_message" ]; then
        user_message="Schedule a meeting and check my documents"
    fi

    run_scenario "$token" "$name" "$role" "$email" \
        "$user_message" '{}' ""
    success "Custom scenario complete"
}

# =============================================================================
# Banner
# =============================================================================
show_banner() {
    clear
    echo ""
    echo -e "${BOLD}${CYAN}"
    echo "    ___                    __     ____  ___    __  ___"
    echo "   /   | ____ ____  ____  / /_   /  _/ /   |  /  |/  /"
    echo "  / /| |/ __ \`/ _ \\/ __ \\/ __/   / /  / /| | / /|_/ / "
    echo " / ___ / /_/ /  __/ / / / /_   _/ /  / ___ |/ /  / /  "
    echo "/_/  |_\\__, /\\___/_/ /_/\\__/  /___/ /_/  |_/_/  /_/   "
    echo "      /____/                                           "
    echo -e "${NC}"
    echo -e "${BOLD}  Delegation E2E Demo — Interactive Mode${NC}"
    echo -e "${DIM}  3 services · 3 user roles · depth-4 delegation · scope attenuation${NC}"
    echo ""
}

# =============================================================================
# Phase 1: Auto-setup
# =============================================================================
phase_setup() {
    section "SETUP: Registering users & agent"
    echo ""

    # Register Alice
    local tmpfile=$(mktemp)
    (curl -s -X POST "$BASE_URL/register" \
        -H "Content-Type: application/json" \
        -d '{"email": "alice@example.com", "password": "SecurePass123!", "display_name": "Alice", "role": "admin"}' > "$tmpfile" 2>&1) &
    spinner $! "Registering Alice (admin)..."
    success "Alice registered as ${BOLD}admin${NC}"

    # Register Bob
    (curl -s -X POST "$BASE_URL/register" \
        -H "Content-Type: application/json" \
        -d '{"email": "bob@example.com", "password": "SecurePass123!", "display_name": "Bob", "role": "member"}' > "$tmpfile" 2>&1) &
    spinner $! "Registering Bob (member)..."
    success "Bob registered as ${BOLD}member${NC}"

    # Register Carol
    (curl -s -X POST "$BASE_URL/register" \
        -H "Content-Type: application/json" \
        -d '{"email": "carol@example.com", "password": "SecurePass123!", "display_name": "Carol", "role": "viewer"}' > "$tmpfile" 2>&1) &
    spinner $! "Registering Carol (viewer)..."
    success "Carol registered as ${BOLD}viewer${NC}"

    echo ""

    # Login all users
    (ALICE_TOKEN_TMP=$(curl -s -X POST "$BASE_URL/login" \
        -H "Content-Type: application/json" \
        -d '{"email": "alice@example.com", "password": "SecurePass123!"}' | jq -r '.access_token // empty')
    echo "$ALICE_TOKEN_TMP" > "$tmpfile") &
    spinner $! "Logging in Alice..."
    ALICE_TOKEN=$(cat "$tmpfile")
    if [ -z "$ALICE_TOKEN" ]; then fail "Alice login failed"; exit 1; fi
    success "Alice authenticated"

    local tmpfile2=$(mktemp)
    (BOB_TOKEN_TMP=$(curl -s -X POST "$BASE_URL/login" \
        -H "Content-Type: application/json" \
        -d '{"email": "bob@example.com", "password": "SecurePass123!"}' | jq -r '.access_token // empty')
    echo "$BOB_TOKEN_TMP" > "$tmpfile2") &
    spinner $! "Logging in Bob..."
    BOB_TOKEN=$(cat "$tmpfile2")
    if [ -z "$BOB_TOKEN" ]; then fail "Bob login failed"; exit 1; fi
    success "Bob authenticated"

    local tmpfile3=$(mktemp)
    (CAROL_TOKEN_TMP=$(curl -s -X POST "$BASE_URL/login" \
        -H "Content-Type: application/json" \
        -d '{"email": "carol@example.com", "password": "SecurePass123!"}' | jq -r '.access_token // empty')
    echo "$CAROL_TOKEN_TMP" > "$tmpfile3") &
    spinner $! "Logging in Carol..."
    CAROL_TOKEN=$(cat "$tmpfile3")
    if [ -z "$CAROL_TOKEN" ]; then fail "Carol login failed"; exit 1; fi
    success "Carol authenticated"

    rm -f "$tmpfile" "$tmpfile2" "$tmpfile3"

    echo ""

    # Register worker sub-agents (owned by Alice, used by AIP backend for depth-4 delegation)
    local worker_tmp=$(mktemp)
    (curl -s -X POST "$BASE_URL/agents/register" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ALICE_TOKEN" \
        -d '{"name": "calendar-worker", "agent_type": "worker", "allowed_scopes": ["calendar:read", "calendar:write"]}' > "$worker_tmp" 2>&1) &
    spinner $! "Registering calendar-worker..."
    success "calendar-worker registered"

    (curl -s -X POST "$BASE_URL/agents/register" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ALICE_TOKEN" \
        -d '{"name": "comms-worker", "agent_type": "worker", "allowed_scopes": ["slack:post", "notion:read", "gmail:send"]}' > "$worker_tmp" 2>&1) &
    spinner $! "Registering comms-worker..."
    success "comms-worker registered"
    rm -f "$worker_tmp"

    # Register orchestrator agent
    local agent_tmp=$(mktemp)
    (curl -s -X POST "$BASE_URL/agents/register" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ALICE_TOKEN" \
        -d '{"name": "scheduling-agent", "agent_type": "orchestrator", "allowed_scopes": ["calendar:read", "calendar:write", "slack:post", "notion:read"]}' > "$agent_tmp" 2>&1) &
    spinner $! "Registering scheduling-agent..."
    AGENT_ID=$(cat "$agent_tmp" | jq -r '.id // empty')
    rm -f "$agent_tmp"

    if [ -z "$AGENT_ID" ]; then
        fail "Agent registration failed"
        exit 1
    fi
    success "Agent registered: ${BOLD}$AGENT_ID${NC}"

    # Summary table
    echo ""
    echo -e "  ${BOLD}── Setup Summary ───────────────────────────────────────${NC}"
    echo ""
    echo -e "    User          Role        Expected Scopes"
    echo -e "    ────────────  ──────────  ─────────────────────────────────"
    echo -e "    Alice         ${GREEN}admin${NC}       all 4 agent scopes"
    echo -e "    Bob           ${YELLOW}member${NC}      calendar:r/w, notion:read (no slack)"
    echo -e "    Carol         ${MAGENTA}viewer${NC}      calendar:read, notion:read only"
    echo ""
    echo -e "    ${BOLD}Orchestrator:${NC}  $AGENT_ID"
    echo -e "    ${DIM}Ceiling:       calendar:read, calendar:write, slack:post, notion:read${NC}"
    echo ""
    echo -e "    ${BOLD}Workers:${NC}"
    echo -e "    ${DIM}calendar-worker:  calendar:read, calendar:write${NC}"
    echo -e "    ${DIM}comms-worker:     slack:post, notion:read, gmail:send${NC}"
    echo ""
}

# =============================================================================
# Phase 2: Interactive Menu
# =============================================================================
show_menu() {
    echo ""
    echo -e "  ${BOLD}Choose a scenario:${NC}"
    echo ""
    echo -e "    ${CYAN}[1]${NC} Alice (admin)  -> full scopes"
    echo -e "    ${CYAN}[2]${NC} Bob (member)   -> intersection scopes"
    echo -e "    ${CYAN}[3]${NC} Carol (viewer) -> read-only scopes"
    echo -e "    ${CYAN}[4]${NC} Scope denial   -> gmail:send blocked"
    echo -e "    ${CYAN}[5]${NC} Custom         -> pick user + type message"
    echo ""
    echo -e "    ${GREEN}[a]${NC} Run all        -> execute 1-4 sequentially"
    echo -e "    ${RED}[q]${NC} Quit"
    echo ""
}

interactive_loop() {
    while true; do
        show_menu
        printf "  ${BOLD}>${NC} "
        read -r choice

        case "$choice" in
            1) scenario_alice ;;
            2) scenario_bob ;;
            3) scenario_carol ;;
            4) scenario_denial ;;
            5) scenario_custom ;;
            a|A)
                scenario_alice
                echo ""
                echo -e "  ${DIM}─── next scenario ───${NC}"
                sleep 1
                scenario_bob
                echo ""
                echo -e "  ${DIM}─── next scenario ───${NC}"
                sleep 1
                scenario_carol
                echo ""
                echo -e "  ${DIM}─── next scenario ───${NC}"
                sleep 1
                scenario_denial

                echo ""
                section "ALL SCENARIOS COMPLETE"
                echo ""
                echo -e "  ${BOLD}Summary:${NC}"
                echo -e "    ${GREEN}1.${NC} Admin   -> full agent scopes   -> all tools executed"
                echo -e "    ${YELLOW}2.${NC} Member  -> intersection scopes  -> some tools available"
                echo -e "    ${MAGENTA}3.${NC} Viewer  -> read-only scopes     -> only read tools"
                echo -e "    ${RED}4.${NC} Ceiling -> gmail:send denied    -> not in allowed_scopes"
                echo ""
                echo -e "  ${BOLD}Key concepts demonstrated:${NC}"
                echo -e "    ${DIM}Depth-4 delegation: User -> Orchestrator -> Worker -> Tool${NC}"
                echo -e "    ${DIM}Stateless JWT delegation (no DB write on token path)${NC}"
                echo -e "    ${DIM}Scope attenuation at every level (child subset of parent)${NC}"
                echo -e "    ${DIM}Same agent, different origins -> different effective scopes${NC}"
                echo -e "    ${DIM}4 enforcement points (user -> orchestrator -> worker -> tool)${NC}"
                echo -e "    ${DIM}Audit trail via delegation_ref across all services${NC}"
                echo ""
                ;;
            q|Q)
                echo ""
                echo -e "  ${DIM}Goodbye!${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo -e "  ${RED}Invalid choice.${NC} Pick 1-5, a, or q."
                ;;
        esac
    done
}

# =============================================================================
# Main
# =============================================================================

show_banner

# Check services are running
for port in 8000 8001 8002; do
    if ! curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
        fail "Service on port $port is not responding."
        echo -e "  ${DIM}Run: make start-services${NC}"
        exit 1
    fi
done
success "All 3 services are healthy (depth-4 delegation ready)"

phase_setup
interactive_loop
