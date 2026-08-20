#!/usr/bin/env bash
set -euo pipefail

# Compose loads .env automatically, but this script runs in the host shell.
# Read only the Metabase settings so unrelated dotenv values are not evaluated
# as shell syntax.
if [[ -f .env ]]; then
  while IFS= read -r line; do
    case "${line}" in
      METABASE_URL=*)
        [[ -n "${METABASE_URL+x}" ]] || export "${line}"
        ;;
      METABASE_ADMIN_EMAIL=*)
        [[ -n "${METABASE_ADMIN_EMAIL+x}" ]] || export "${line}"
        ;;
      METABASE_ADMIN_PASSWORD=*)
        [[ -n "${METABASE_ADMIN_PASSWORD+x}" ]] || export "${line}"
        ;;
      DB_NAME=*)
        [[ -n "${DB_NAME+x}" ]] || export "${line}"
        ;;
      DB_USER=*)
        [[ -n "${DB_USER+x}" ]] || export "${line}"
        ;;
      DB_PASSWORD=*)
        [[ -n "${DB_PASSWORD+x}" ]] || export "${line}"
        ;;
      DB_PORT=*)
        [[ -n "${DB_PORT+x}" ]] || export "${line}"
        ;;
      METABASE_DATABASE_HOST=*)
        [[ -n "${METABASE_DATABASE_HOST+x}" ]] || export "${line}"
        ;;
      METABASE_HEALTH_TIMEOUT_SECONDS=*)
        [[ -n "${METABASE_HEALTH_TIMEOUT_SECONDS+x}" ]] || export "${line}"
        ;;
    esac
  done < .env
fi

METABASE_URL="${METABASE_URL:-http://127.0.0.1:3000}"
ADMIN_EMAIL="${METABASE_ADMIN_EMAIL:?METABASE_ADMIN_EMAIL is required}"
ADMIN_PASSWORD="${METABASE_ADMIN_PASSWORD:?METABASE_ADMIN_PASSWORD is required}"
DB_NAME="${DB_NAME:?DB_NAME is required}"
DB_USER="${DB_USER:?DB_USER is required}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD is required}"
DB_PORT="${DB_PORT:-5432}"
DATABASE_NAME="${METABASE_DATABASE_NAME:-AI Tour Guide}"
DATABASE_HOST="${METABASE_DATABASE_HOST:-database}"
HEALTH_TIMEOUT_SECONDS="${METABASE_HEALTH_TIMEOUT_SECONDS:-300}"

if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
  echo 'curl and jq are required to bootstrap Metabase.' >&2
  exit 1
fi

echo "Waiting for Metabase at ${METABASE_URL}..."
echo "Initializing Metabase. This might take a few minutes."
health_started_at=$(date +%s)
while true; do
  if health_response=$(curl --fail --silent --noproxy '*' \
    --write-out $'\n%{http_code}' "${METABASE_URL}/api/health"); then
    break
  fi
  if (( $(date +%s) - health_started_at >= HEALTH_TIMEOUT_SECONDS )); then
    health_response=$(curl --silent --show-error --noproxy '*' \
      --write-out $'\n%{http_code}' "${METABASE_URL}/api/health" || true)
    health_status=${health_response##*$'\n'}
    health_body=${health_response%$'\n'*}
    echo "Metabase did not become healthy within ${HEALTH_TIMEOUT_SECONDS} seconds (HTTP ${health_status}): ${health_body}" >&2
    exit 1
  fi
  sleep 2
done

health_status=${health_response##*$'\n'}
health_body=${health_response%$'\n'*}
if [[ "${health_status}" != 200 ]]; then
  echo "Metabase health check failed (HTTP ${health_status}): ${health_body}" >&2
  exit 1
fi

properties_response=$(curl --silent --show-error --noproxy '*' \
  --write-out $'\n%{http_code}' "${METABASE_URL}/api/session/properties")
properties_status=${properties_response##*$'\n'}
properties=${properties_response%$'\n'*}
if [[ "${properties_status}" != 200 ]]; then
  echo "Metabase properties request failed (HTTP ${properties_status}): ${properties}" >&2
  exit 1
fi
setup_token=$(jq -r '."setup-token" // empty' <<<"${properties}")

if [[ -z "${setup_token}" ]]; then
  echo 'Metabase is already initialized.'
  session_response=$(jq -n \
    --arg email "${ADMIN_EMAIL}" \
    --arg password "${ADMIN_PASSWORD}" \
    '{username: $email, password: $password}' | \
    curl --silent --show-error --noproxy '*' \
      --write-out $'\n%{http_code}' \
      -X POST "${METABASE_URL}/api/session" \
      -H 'Content-Type: application/json' \
      --data-binary @-)
  session_status=${session_response##*$'\n'}
  session_body=${session_response%$'\n'*}
  if ! session_id=$(jq -er '.id // empty' <<<"${session_body}"); then
    echo "Metabase login returned a non-JSON response (HTTP ${session_status}): ${session_body}" >&2
    exit 1
  fi
  if [[ "${session_status}" != 200 ]]; then
    echo "Metabase login failed (HTTP ${session_status}): ${session_body}" >&2
  fi
else
  payload=$(jq -n \
    --arg token "${setup_token}" \
    --arg email "${ADMIN_EMAIL}" \
    --arg password "${ADMIN_PASSWORD}" \
    '{
      token: $token,
      user: {
        email: $email,
        first_name: "Metabase",
        last_name: "Admin",
        password: $password
      },
      prefs: {
        allow_tracking: false,
        site_name: "AI Tour Guide"
      }
    }')

  setup_response=$(curl --silent --show-error --noproxy '*' \
    --write-out $'\n%{http_code}' \
    -X POST "${METABASE_URL}/api/setup" \
    -H 'Content-Type: application/json' \
    --data-raw "${payload}")
  setup_status=${setup_response##*$'\n'}
  setup_body=${setup_response%$'\n'*}
  if [[ "${setup_status}" != 200 ]]; then
    echo "Metabase setup failed (HTTP ${setup_status}): ${setup_body}" >&2
    exit 1
  fi
  session_status=${setup_status}
  session_id=$(jq -r '.id // empty' <<<"${setup_body}")
  echo "Created Metabase admin user ${ADMIN_EMAIL}."
fi

if [[ "${session_status}" != 200 || -z "${session_id}" ]]; then
  exit 1
fi

databases=$(curl --fail --silent --show-error --noproxy '*' \
  "${METABASE_URL}/api/database" \
  -H "X-Metabase-Session: ${session_id}")

configure_database() {
  local name=$1
  local schema=$2
  local database_id
  local database_payload

  database_id=$(jq -r --arg name "${name}" \
    '.data[]? | select(.name == $name) | .id' <<<"${databases}" | head -n 1)
  database_payload=$(jq -n \
    --arg name "${name}" \
    --arg schema "${schema}" \
    --arg dbname "${DB_NAME}" \
    --arg user "${DB_USER}" \
    --arg password "${DB_PASSWORD}" \
    --arg host "${DATABASE_HOST}" \
    --arg port "${DB_PORT}" \
    '{
      name: $name,
      engine: "postgres",
      details: {
        host: $host,
        port: ($port | tonumber),
        dbname: $dbname,
        user: $user,
        password: $password,
        "schema-filters-type": "inclusion",
        "schema-filters-patterns": $schema
      }
    }')

  if [[ -n "${database_id}" ]]; then
    curl --fail --silent --show-error --noproxy '*' \
      -X PUT "${METABASE_URL}/api/database/${database_id}" \
      -H "X-Metabase-Session: ${session_id}" \
      -H 'Content-Type: application/json' \
      --data-raw "${database_payload}" >/dev/null
    echo "Updated PostgreSQL database ${name} in Metabase."
  else
    curl --fail --silent --show-error --noproxy '*' \
      -X POST "${METABASE_URL}/api/database" \
      -H "X-Metabase-Session: ${session_id}" \
      -H 'Content-Type: application/json' \
      --data-raw "${database_payload}" >/dev/null
    echo "Added PostgreSQL database ${name} to Metabase."
  fi
}

configure_database 'AI Tour Guide - Public' public
configure_database 'AI Tour Guide - Evaluation' evaluation
