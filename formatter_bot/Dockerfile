FROM aiogram/telegram-bot-api:latest AS tgapi

FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --from=tgapi /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

COPY . /app

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
