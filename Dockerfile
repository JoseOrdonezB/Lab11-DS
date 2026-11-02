FROM python:3.12-slim

WORKDIR /app


COPY pipeline ./pipeline
COPY config ./config
COPY scripts ./scripts
COPY tests ./tests

EXPOSE 8501 5000

