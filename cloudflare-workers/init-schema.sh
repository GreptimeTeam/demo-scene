#!/bin/sh
# Apply schema.sql to GreptimeDB once it's healthy. One-shot, idempotent
# (schema.sql uses IF NOT EXISTS).
set -eu

GREPTIME_URL="${GREPTIME_URL:-http://greptimedb:4000}"
DB="${GREPTIME_DB:-public}"
SQL_FILE="${SQL_FILE:-/schema.sql}"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-60}"

echo "==> waiting for GreptimeDB at ${GREPTIME_URL} ..."
elapsed=0
until curl -sf -o /dev/null "${GREPTIME_URL}/health"; do
    if [ "$elapsed" -ge "$WAIT_TIMEOUT_SECONDS" ]; then
        echo "ERROR: GreptimeDB not ready after ${WAIT_TIMEOUT_SECONDS}s"; exit 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done
echo "    ready."

echo "==> applying ${SQL_FILE} to db=${DB} ..."
if [ ! -f "$SQL_FILE" ]; then
    echo "ERROR: SQL file not found: ${SQL_FILE}"; exit 1
fi

# Strip comments, collapse whitespace, split on semicolons, execute each.
sed 's/--.*$//' "$SQL_FILE" | tr '\n' ' ' | tr ';' '\n' > /tmp/stmts.txt
while IFS= read -r stmt; do
    stmt=$(echo "$stmt" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$stmt" ] && continue
    echo "  -> $(echo "$stmt" | cut -c1-80)..."
    resp=$(curl -sf -X POST "${GREPTIME_URL}/v1/sql?db=${DB}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "sql=${stmt}" 2>&1) || {
        echo "     FAILED: ${resp}"; exit 1
    }
    echo "     OK"
done < /tmp/stmts.txt

echo "==> schema applied."
