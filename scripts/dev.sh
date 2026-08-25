#!/usr/bin/env bash
# Start the backend and frontend for local development.
#
# Usage:
#   ./scripts/dev.sh                Full stack
#   ./scripts/dev.sh --backend      Backend only
#   ./scripts/dev.sh --frontend     Frontend only
#   ./scripts/dev.sh --no-azure     Full stack without the Azure CLI login check
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
AZURITE_CONTAINER_NAME="${AZURITE_CONTAINER_NAME:-visionary-lab-azurite}"
AZURITE_IMAGE="${AZURITE_IMAGE:-mcr.microsoft.com/azure-storage/azurite:3.35.0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

is_placeholder() {
  local value="${1:-}"
  [[ -z "$value" || "$value" == *"your-"* || "$value" == *"<"* ]]
}

uses_development_storage() {
  [[ "${AZURE_STORAGE_CONNECTION_STRING:-}" == "UseDevelopmentStorage=true" ]]
}

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ ! -f "$ENV_EXAMPLE" ]]; then
      echo -e "${RED}Error: neither .env nor .env.example exists.${NC}" >&2
      exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo -e "${YELLOW}Created .env from .env.example.${NC}"
  fi

  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  local required=(
    AI_FOUNDRY_ENDPOINT
    LLM_DEPLOYMENT
    IMAGEGEN_2_DEPLOYMENT
  )
  if [[ "$mode" != "--backend" ]] && ! uses_development_storage; then
    required+=(AZURE_BLOB_SERVICE_URL AZURE_STORAGE_ACCOUNT_NAME)
  fi
  if [[ "${IMAGE_JOB_MODE:-memory}" == "azure" ]]; then
    required+=(AZURE_STORAGE_QUEUE_URL AZURE_COSMOS_DB_ENDPOINT)
  fi

  local missing=()
  local name
  for name in "${required[@]}"; do
    if is_placeholder "${!name:-}"; then
      missing+=("$name")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo -e "${RED}Configure these values in $ENV_FILE before starting:${NC}" >&2
    printf '  - %s\n' "${missing[@]}" >&2
    echo -e "${YELLOW}Backend-only model testing does not require Blob, Queue, or Cosmos configuration.${NC}" >&2
    echo -e "${YELLOW}Local jobs default to IMAGE_JOB_MODE=memory; Azure mode also requires reachable Queue and Cosmos endpoints.${NC}" >&2
    exit 1
  fi

  echo -e "${GREEN}.env loaded${NC}"
}

start_azurite() {
  if ! uses_development_storage; then
    return
  fi
  if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}Docker is required for AZURE_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true.${NC}" >&2
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}Docker is installed but the daemon is not available.${NC}" >&2
    exit 1
  fi

  if docker container inspect "$AZURITE_CONTAINER_NAME" >/dev/null 2>&1; then
    if [[ "$(docker inspect --format '{{.State.Running}}' "$AZURITE_CONTAINER_NAME")" == "true" ]]; then
      echo -e "${GREEN}Reusing running Azurite container: ${AZURITE_CONTAINER_NAME}${NC}"
    else
      echo -e "${CYAN}Starting existing Azurite container: ${AZURITE_CONTAINER_NAME}${NC}"
      docker start "$AZURITE_CONTAINER_NAME" >/dev/null
      AZURITE_STARTED_BY_SCRIPT=1
    fi
  else
    echo -e "${CYAN}Starting Azurite Blob emulator on 127.0.0.1:10000...${NC}"
    docker run --detach --rm \
      --name "$AZURITE_CONTAINER_NAME" \
      --publish 127.0.0.1:10000:10000 \
      "$AZURITE_IMAGE" \
      azurite-blob --blobHost 0.0.0.0 >/dev/null
    AZURITE_STARTED_BY_SCRIPT=1
    AZURITE_CREATED_BY_SCRIPT=1
  fi

  if command -v curl >/dev/null 2>&1; then
    local attempt
    for attempt in {1..30}; do
      if curl --silent --output /dev/null \
        --connect-timeout 1 \
        http://127.0.0.1:10000/devstoreaccount1; then
        echo -e "${GREEN}Azurite Blob endpoint is ready${NC}"
        return
      fi
      sleep 0.2
    done
    echo -e "${RED}Azurite did not become ready on 127.0.0.1:10000.${NC}" >&2
    exit 1
  fi
}

ensure_azure_auth() {
  if [[ -n "${AZURE_CLIENT_ID:-}" && -n "${AZURE_TENANT_ID:-}" && -n "${AZURE_CLIENT_SECRET:-}" ]]; then
    echo -e "${GREEN}Azure EnvironmentCredential configured${NC}"
    return
  fi
  if ! command -v az >/dev/null 2>&1; then
    echo -e "${RED}Azure CLI is required for local DefaultAzureCredential authentication.${NC}" >&2
    exit 1
  fi
  if ! az account show --output none >/dev/null 2>&1; then
    echo -e "${RED}No Azure CLI session found. Run: az login${NC}" >&2
    exit 1
  fi
  echo -e "${GREEN}Azure CLI authentication available${NC}"
}

cleanup() {
  if [[ -n "${CLEANUP_DONE:-}" ]]; then
    return
  fi
  CLEANUP_DONE=1
  echo -e "\n${CYAN}Shutting down...${NC}"
  if [[ -n "${BACKEND_PID:-}" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  wait 2>/dev/null || true
  if [[ -n "${AZURITE_STARTED_BY_SCRIPT:-}" ]]; then
    docker stop --timeout 3 "$AZURITE_CONTAINER_NAME" >/dev/null 2>&1 || true
    if [[ -n "${AZURITE_CREATED_BY_SCRIPT:-}" ]]; then
      echo -e "${GREEN}Stopped local Azurite container${NC}"
    else
      echo -e "${GREEN}Restored existing Azurite container to stopped state${NC}"
    fi
  fi
}
trap cleanup EXIT INT TERM

start_backend() {
  if ! command -v uv >/dev/null 2>&1; then
    echo -e "${RED}uv is required. Install it from https://docs.astral.sh/uv/${NC}" >&2
    exit 1
  fi
  echo -e "${CYAN}Starting backend on :${BACKEND_PORT}...${NC}"
  (
    cd "$ROOT_DIR"
    uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT"
  ) &
  BACKEND_PID=$!
}

start_frontend() {
  if ! command -v npm >/dev/null 2>&1; then
    echo -e "${RED}npm is required.${NC}" >&2
    exit 1
  fi
  if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
    echo -e "${CYAN}Installing frontend dependencies...${NC}"
    (cd "$ROOT_DIR/frontend" && npm ci)
  fi
  echo -e "${CYAN}Starting frontend on :${FRONTEND_PORT}...${NC}"
  (
    cd "$ROOT_DIR/frontend"
    BACKEND_API_URL="http://127.0.0.1:${BACKEND_PORT}" \
      NEXT_PUBLIC_API_PROTOCOL=http \
      NEXT_PUBLIC_API_HOSTNAME=127.0.0.1 \
      NEXT_PUBLIC_API_PORT="$BACKEND_PORT" \
      PORT="$FRONTEND_PORT" \
      npm run dev
  ) &
  FRONTEND_PID=$!
}

mode="${1:-all}"
case "$mode" in
  --backend)
    ensure_env
    ensure_azure_auth
    start_backend
    ;;
  --frontend)
    start_frontend
    ;;
  --no-azure)
    ensure_env
    start_azurite
    start_backend
    start_frontend
    ;;
  all)
    ensure_env
    ensure_azure_auth
    start_azurite
    start_backend
    start_frontend
    ;;
  *)
    echo "Unknown option: $mode" >&2
    exit 2
    ;;
esac

if [[ -n "${BACKEND_PID:-}" ]]; then
  echo -e "${GREEN}Backend:  http://localhost:${BACKEND_PORT}${NC}"
fi
if [[ -n "${FRONTEND_PID:-}" ]]; then
  echo -e "${GREEN}Frontend: http://localhost:${FRONTEND_PORT}${NC}"
fi
echo -e "${CYAN}Press Ctrl+C to stop.${NC}"
wait
