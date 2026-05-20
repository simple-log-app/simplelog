FROM python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pyqt6 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*
