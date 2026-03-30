# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.base.txt requirements.api.txt requirements.worker.txt requirements.dev.txt requirements.txt ./

RUN pip install --upgrade pip setuptools wheel
RUN pip wheel --wheel-dir /wheels/api -r requirements.api.txt
RUN pip wheel --wheel-dir /wheels/worker -r requirements.worker.txt

FROM base AS dev

COPY requirements.base.txt requirements.api.txt requirements.worker.txt requirements.dev.txt requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS api-runtime

COPY requirements.base.txt requirements.api.txt ./
COPY --from=builder /wheels/api /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.api.txt && rm -rf /wheels

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker-runtime

# Install ffmpeg for video generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.base.txt requirements.api.txt requirements.worker.txt ./
COPY --from=builder /wheels/worker /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.worker.txt && rm -rf /wheels

COPY . .

CMD ["python", "worker.py"]
