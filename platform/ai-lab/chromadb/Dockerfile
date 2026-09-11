FROM python:3.11-slim
WORKDIR /app
COPY embedding_pipeline.py .
RUN pip install --no-cache-dir \
    chromadb==0.5.0 \
    requests \
    psycopg2-binary
ENTRYPOINT ["python3", "embedding_pipeline.py"]
