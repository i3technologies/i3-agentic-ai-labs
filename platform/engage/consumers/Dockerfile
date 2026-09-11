FROM image-registry.openshift-image-registry.svc:5000/openshift/python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends librdkafka-dev gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY kafka_consumers.py .
RUN useradd -m -u 1001 consumer && chown -R consumer /app
USER consumer
CMD ["python", "kafka_consumers.py"]
