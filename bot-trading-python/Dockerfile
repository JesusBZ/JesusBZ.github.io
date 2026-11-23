FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

RUN groupadd --gid 10001 quantbot \
    && useradd --uid 10001 --gid quantbot --shell /usr/sbin/nologin --create-home quantbot

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip==24.3.1 \
    && pip install --no-cache-dir --only-binary=:all: -r requirements.txt

COPY --chown=quantbot:quantbot . .

USER quantbot

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"10000\")}/health', timeout=4).read()" || exit 1

CMD ["python", "-B", "main.py", "--daemon-intraday", "--serve-web", "--interval", "60"]
