FROM python:3.13-slim

RUN apt-get update     && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

RUN set -eux;     arch="$(dpkg --print-architecture)";     case "$arch" in       amd64) tg_arch="x86_64" ;;       arm64) tg_arch="aarch64" ;;       *) echo "Unsupported architecture: $arch"; exit 1 ;;     esac;     curl -L "https://github.com/tdlib/telegram-bot-api/releases/latest/download/telegram-bot-api-linux-${tg_arch}.tar.gz" -o /tmp/telegram-bot-api.tar.gz;     tar -xzf /tmp/telegram-bot-api.tar.gz -C /tmp;     mv /tmp/telegram-bot-api/bin/telegram-bot-api /usr/local/bin/telegram-bot-api;     chmod +x /usr/local/bin/telegram-bot-api;     rm -rf /tmp/telegram-bot-api /tmp/telegram-bot-api.tar.gz

COPY . /app
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
