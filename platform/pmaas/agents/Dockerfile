FROM image-registry.openshift-image-registry.svc:5000/openshift/python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY campaign_agent.py .

RUN useradd -m -u 1001 agent
USER agent

EXPOSE 8080
CMD ["uvicorn", "campaign_agent:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
