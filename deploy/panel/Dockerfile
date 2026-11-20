FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# PySpark necesita una JVM; openjdk-17 es la versión estable para Spark 3.5/4.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY deploy/panel/requirements.txt /app/deploy/panel/requirements.txt
RUN pip install -r /app/deploy/panel/requirements.txt

COPY src /app/src
COPY sql /app/sql
COPY data/reference /app/data/reference
COPY powerbi /app/powerbi
COPY deploy/panel /app/deploy/panel

RUN mkdir -p /app/config /app/data/logs /app/data/raw /app/data/staging

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "app:app", "--app-dir", "deploy/panel", "--host", "0.0.0.0", "--port", "8000"]
