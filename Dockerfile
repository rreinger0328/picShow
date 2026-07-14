FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PICSHOW_MEDIA_DIR=/app/media \
    PICSHOW_CACHE_DIR=/app/.picshow-cache \
    PICSHOW_THUMBNAIL_SIZE=640 \
    PICSHOW_ZOOM_PREVIEW_SIZE=2200 \
    PORT=5000

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

RUN apt-get update \
    && apt-get install -y --no-install-recommends libheif1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/media /app/.picshow-cache && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "app:app"]
