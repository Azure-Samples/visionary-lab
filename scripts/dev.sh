#!/usr/bin/env bash
# dev.sh — Start backend + frontend locally for fast iteration.
# Usage: ./scripts/dev.sh              (full stack + Azure access setup)
#        ./scripts/dev.sh --no-azure   (full stack, skip Azure tagging)
#        ./scripts/dev.sh --backend    (backend only)
#        ./scripts/dev.sh --frontend   (frontend only)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── .env bootstrap ──────────────────────────────────────────────────
ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
      echo -e "${YELLOW}No .env file found. Creating one from .env.example...${NC}"
      cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
      echo -e "${RED}Error: No .env or .env.example found.${NC}" >&2
      exit 1
    fi
  fi

  # Load current .env
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  # Check for placeholder values and prompt the user
  local missing=()
  local vars=(
    "IMAGEGEN_AOAI_RESOURCE:Image generation resource name"
    "IMAGEGEN_DEPLOYMENT:Image generation deployment name (e.g. gpt-image-1)"
    "IMAGEGEN_15_DEPLOYMENT:Image 1.5 deployment name (e.g. gpt-image-1.5)"
    "IMAGEGEN_1_MINI_DEPLOYMENT:Image 1 Mini deployment name (e.g. gpt-image-1-mini)"
    "IMAGEGEN_AOAI_API_KEY:Image generation API key"
    "LLM_AOAI_RESOURCE:LLM resource name"
    "LLM_DEPLOYMENT:LLM deployment name (e.g. gpt-4.1)"
    "LLM_AOAI_API_KEY:LLM API key"
    "AZURE_STORAGE_ACCOUNT_NAME:Azure Storage account name"
    "AZURE_STORAGE_ACCOUNT_KEY:Azure Storage account key"
    "AZURE_BLOB_SERVICE_URL:Azure Blob service URL"
    "AZURE_COSMOS_DB_ENDPOINT:Cosmos DB endpoint"
    "AZURE_COSMOS_DB_KEY:Cosmos DB key"
    "AZURE_COSMOS_DB_ID:Cosmos DB database ID"
    "AZURE_COSMOS_CONTAINER_ID:Cosmos DB container ID"
  )

  for entry in "${vars[@]}"; do
    local var_name="${entry%%:*}"
    local var_desc="${entry#*:}"
    local val="${!var_name:-}"
    # Flag if empty or still a placeholder from .env.example
    if [[ -z "$val" || "$val" == your-* || "$val" == *"<name_of_"* ]]; then
      missing+=("$var_name")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}══════════════════════════════════════${NC}"
    echo -e "${YELLOW}  Missing or placeholder env vars${NC}"
    echo -e "${YELLOW}══════════════════════════════════════${NC}"
    echo ""
    for entry in "${vars[@]}"; do
      local var_name="${entry%%:*}"
      local var_desc="${entry#*:}"
      # Only prompt for missing ones
      local found=false
      for m in "${missing[@]}"; do
        if [[ "$m" == "$var_name" ]]; then found=true; break; fi
      done
      if ! $found; then continue; fi

      local current="${!var_name:-}"
      echo -e "${CYAN}${var_desc}${NC} (${var_name})"
      if [[ -n "$current" && "$current" != your-* && "$current" != *"<name_of_"* ]]; then
        echo -e "  Current: ${current}"
      fi
      read -rp "  Value (enter to skip): " new_val
      if [[ -n "$new_val" ]]; then
        # Update or append to .env
        if grep -q "^${var_name}=" "$ENV_FILE" 2>/dev/null; then
          # Use a temp file for cross-platform sed compatibility
          local tmp; tmp=$(mktemp)
          awk -v key="$var_name" -v val="$new_val" 'BEGIN{FS=OFS="="} $1==key{$2=val}{print}' "$ENV_FILE" > "$tmp"
          mv "$tmp" "$ENV_FILE"
        else
          echo "${var_name}=${new_val}" >> "$ENV_FILE"
        fi
        export "$var_name=$new_val"
      fi
    done
    echo ""

    # Re-source after updates
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi

  echo -e "${GREEN}.env loaded ✓${NC}"
}

ensure_azure_access() {
  local ALLOW_SCRIPT="$ROOT_DIR/scripts/allow-local-access.sh"
  if [[ -x "$ALLOW_SCRIPT" ]]; then
    echo -e "${CYAN}Ensuring Azure resource access for local dev...${NC}"
    "$ALLOW_SCRIPT"
  else
    echo -e "${YELLOW}Skipping Azure access setup (scripts/allow-local-access.sh not found)${NC}"
  fi
}

cleanup() {
  echo -e "\n${CYAN}Shutting down...${NC}"
  # Kill child processes
  if [[ -n "${BACKEND_PID:-}" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  wait 2>/dev/null
  echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

start_backend() {
  echo -e "${CYAN}Starting backend on :${BACKEND_PORT}...${NC}"
  cd "$ROOT_DIR"
  if ! command -v uv &>/dev/null; then
    echo -e "${RED}Error: uv not found. Install it: https://docs.astral.sh/uv/${NC}" >&2
    exit 1
  fi
  uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" &
  BACKEND_PID=$!
  echo -e "${GREEN}Backend PID: ${BACKEND_PID}${NC}"
}

start_frontend() {
  echo -e "${CYAN}Starting frontend on :${FRONTEND_PORT}...${NC}"
  cd "$ROOT_DIR/frontend"
  if [[ ! -d node_modules ]]; then
    echo -e "${CYAN}Installing frontend dependencies...${NC}"
    npm install --silent
  fi
  PORT=$FRONTEND_PORT npm run dev &
  FRONTEND_PID=$!
  echo -e "${GREEN}Frontend PID: ${FRONTEND_PID}${NC}"
}

case "${1:-all}" in
  --backend)  ensure_env; ensure_azure_access; start_backend; wait "$BACKEND_PID" ;;
  --frontend) start_frontend; wait "$FRONTEND_PID" ;;
  --no-azure)
    ensure_env
    echo -e "${CYAN}══════════════════════════════════════${NC}"
    echo -e "${CYAN}  Visionary Lab — Local Dev Server${NC}"
    echo -e "${YELLOW}  (skipping Azure access setup)${NC}"
    echo -e "${CYAN}══════════════════════════════════════${NC}"
    echo ""
    start_backend
    start_frontend
    echo ""
    echo -e "${GREEN}Backend:  http://localhost:${BACKEND_PORT}${NC}"
    echo -e "${GREEN}Frontend: http://localhost:${FRONTEND_PORT}${NC}"
    echo -e "${CYAN}Press Ctrl+C to stop both.${NC}"
    echo ""
    wait
    ;;
  *)
    ensure_env
    ensure_azure_access
    echo -e "${CYAN}══════════════════════════════════════${NC}"
    echo -e "${CYAN}  Visionary Lab — Local Dev Server${NC}"
    echo -e "${CYAN}══════════════════════════════════════${NC}"
    echo ""
    start_backend
    start_frontend
    echo ""
    echo -e "${GREEN}Backend:  http://localhost:${BACKEND_PORT}${NC}"
    echo -e "${GREEN}Frontend: http://localhost:${FRONTEND_PORT}${NC}"
    echo -e "${CYAN}Press Ctrl+C to stop both.${NC}"
    echo ""
    wait
    ;;
esac
