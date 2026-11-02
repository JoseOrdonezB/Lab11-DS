FROM python:3.12-slim

WORKDIR /app

COPY requirements-pipeline.txt ./
RUN pip install --no-cache-dir -r requirements-pipeline.txt "streamlit>=1.40" "plotly>=5.24"

COPY app ./app
COPY pipeline ./pipeline
COPY config ./config
COPY scripts ./scripts
COPY tests ./tests

ARG GIT_COMMIT=sin-git
ENV GIT_COMMIT=${GIT_COMMIT}

EXPOSE 8501 5000

CMD ["streamlit", "run", "app/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
