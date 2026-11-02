# Imagen única para el tablero, el pipeline y MLflow (Laboratorio 11).
# Los datos institucionales NO se copian a la imagen: se montan desde data/raw.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MLFLOW_DISABLE_AGENT_HINT=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-pipeline.txt .
RUN pip install --upgrade pip && pip install -r requirements-pipeline.txt

# Código, configuración y datos derivados (data/raw queda fuera por .dockerignore).
COPY pipeline ./pipeline
COPY app ./app
COPY config ./config
COPY scripts ./scripts
COPY tests ./tests
COPY data ./data
COPY published ./published
COPY docs ./docs
COPY README.md .

EXPOSE 8501 5000

# Por defecto se levanta el tablero; docker-compose.yml redefine el comando para
# el pipeline y para el servidor de MLflow.
CMD ["streamlit", "run", "app/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
