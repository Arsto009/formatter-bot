#!/usr/bin/env sh
set -eu

if [ -z "${TELEGRAM_API_ID:-}" ] || [ -z "${TELEGRAM_API_HASH:-}" ]; then
  echo "❌ TELEGRAM_API_ID أو TELEGRAM_API_HASH غير موجود"
  exit 1
fi

export TELEGRAM_LOCAL_MODE="1"
export TELEGRAM_BASE_URL="${TELEGRAM_BASE_URL:-http://127.0.0.1:8081/bot}"
export TELEGRAM_BASE_FILE_URL="${TELEGRAM_BASE_FILE_URL:-http://127.0.0.1:8081/file/bot}"

mkdir -p /var/lib/telegram-bot-api

telegram-bot-api   --api-id="${TELEGRAM_API_ID}"   --api-hash="${TELEGRAM_API_HASH}"   --local   --http-port=8081   --dir=/var/lib/telegram-bot-api   > /tmp/telegram-bot-api.log 2>&1 &

TG_PID=$!

sleep 3

cleanup() {
  kill "$TG_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

exec python -u app.py
