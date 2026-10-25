FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY bot/ /app/bot/
COPY README.md /app/README.md

WORKDIR /app/bot
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
