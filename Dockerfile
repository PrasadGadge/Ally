# Vivie — container for CI / headless testing (mic/UI need host mount for full use)
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-core.txt requirements-optional.txt ./
RUN pip install --no-cache-dir -r requirements-core.txt \
    && pip install --no-cache-dir -r requirements-optional.txt || true

COPY . .

ENV PYTHONUNBUFFERED=1
ENV VIVIE_HEADLESS=1

# Default: run tests (override for Vivie.py on a machine with audio)
CMD ["python", "-m", "pytest", "tests/", "-q", "--tb=line"]
