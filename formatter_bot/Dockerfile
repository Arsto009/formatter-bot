FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# تنزيل telegram-bot-api الجاهز
RUN ARCH="$(dpkg --print-architecture)" && \
    case "$ARCH" in \
      amd64) TG_ARCH="x86_64" ;; \
      arm64) TG_ARCH="aarch64" ;; \
      *) echo "Unsupported arch: $ARCH" && exit 1 ;; \
    esac && \
    curl -L -o /tmp/tgapi.tar.xz "https://github.com/tdlib/telegram-bot-api/releases/latest/download/telegram-bot-api-linux-${TG_ARCH}.tar.xz" && \
    mkdir -p /tmp/tgapi && \
    tar -xJf /tmp/tgapi.tar.xz -C /tmp/tgapi && \
    find /tmp/tgapi -type f -name telegram-bot-api -exec cp {} /usr/local/bin/telegram-bot-api \; && \
    chmod +x /usr/local/bin/telegram-bot-api && \
    rm -rf /tmp/tgapi /tmp/tgapi.tar.xz

COPY . /app

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
