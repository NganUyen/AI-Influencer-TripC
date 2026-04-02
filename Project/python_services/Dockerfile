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

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY requirements.base.txt requirements.api.txt requirements.worker.txt requirements.dev.txt requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS api-runtime

# Install ffmpeg + tesseract for video quality validation and OCR analysis
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY requirements.base.txt requirements.api.txt ./
COPY --from=builder /wheels/api /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.api.txt && rm -rf /wheels

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker-runtime

# Install ffmpeg, tesseract-ocr, and minimal Chromium dependencies in single layer
# Using --no-install-recommends and cleaning in same RUN to minimize layer size
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 libatspi2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY requirements.base.txt requirements.api.txt requirements.worker.txt ./
COPY --from=builder /wheels/worker /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.worker.txt && rm -rf /wheels

# Install Playwright Chromium and clean up cache in same layer
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
RUN playwright install chromium \
    && rm -rf /root/.cache/pip /root/.cache/ms-playwright-build

COPY . .

CMD ["python", "worker.py"]
