#!/bin/sh
set -eu

if [ -z "${TELEGRAM_API_ID:-}" ] || [ -z "${TELEGRAM_API_HASH:-}" ]; then
  echo "❌ TELEGRAM_API_ID / TELEGRAM_API_HASH غير موجودة"
  exit 1
fi

if [ -z "${BOT_TOKEN:-}" ]; then
  echo "❌ BOT_TOKEN غير موجود"
  exit 1
fi

mkdir -p /tmp/tg-bot-api /tmp/tg-bot-api-files

telegram-bot-api \
  --api-id="$TELEGRAM_API_ID" \
  --api-hash="$TELEGRAM_API_HASH" \
  --local \
  --http-port=8081 \
  --dir=/tmp/tg-bot-api \
  --temp-dir=/tmp/tg-bot-api-files \
  >/tmp/telegram-bot-api.log 2>&1 &

sleep 3

export TELEGRAM_LOCAL_MODE=1
export TELEGRAM_BASE_URL="http://127.0.0.1:8081/bot"
export TELEGRAM_BASE_FILE_URL="http://127.0.0.1:8081/file/bot"

python /app/app.py
