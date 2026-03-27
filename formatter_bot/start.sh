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

echo "🚀 Starting telegram-bot-api..."
telegram-bot-api \
  --api-id="$TELEGRAM_API_ID" \
  --api-hash="$TELEGRAM_API_HASH" \
  --local \
  --http-port=8081 \
  --dir=/tmp/tg-bot-api \
  --temp-dir=/tmp/tg-bot-api-files \
  >/tmp/telegram-bot-api.log 2>&1 &

TGAPI_PID=$!

echo "⏳ Waiting for Local Bot API to start..."

i=0
while [ $i -lt 20 ]; do
  if curl -fsS http://127.0.0.1:8081 >/dev/null 2>&1; then
    echo "✅ Local Bot API is up"
    break
  fi

  if ! kill -0 "$TGAPI_PID" 2>/dev/null; then
    echo "❌ telegram-bot-api exited unexpectedly"
    echo "------ telegram-bot-api.log ------"
    cat /tmp/telegram-bot-api.log || true
    echo "----------------------------------"
    exit 1
  fi

  i=$((i + 1))
  sleep 1
done

if ! curl -fsS http://127.0.0.1:8081 >/dev/null 2>&1; then
  echo "❌ Local Bot API did not become ready in time"
  echo "------ telegram-bot-api.log ------"
  cat /tmp/telegram-bot-api.log || true
  echo "----------------------------------"
  exit 1
fi

export TELEGRAM_LOCAL_MODE=1
export TELEGRAM_BASE_URL="http://127.0.0.1:8081/bot"
export TELEGRAM_BASE_FILE_URL="http://127.0.0.1:8081/file/bot"

echo "🚀 Starting app.py..."
python /app/app.py
