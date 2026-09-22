FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1     PORT=8080 DB_PATH=/app/data/vera.sqlite3
WORKDIR /app
RUN groupadd --gid 10001 bot && useradd --uid 10001 --gid bot --no-create-home bot
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY bot.py start.py ./
COPY vera ./vera
COPY deployment/container_entrypoint.py ./deployment/container_entrypoint.py
RUN mkdir -p /app/data && chown -R 10001:10001 /app/data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3   CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/v1/healthz',timeout=3)" || exit 1
# This launcher fixes mounted-disk permissions, then drops to UID/GID 10001.
CMD ["python", "deployment/container_entrypoint.py"]
