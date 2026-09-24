FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY main.py models.py schemas.py __init__.py ./
COPY manifests/ ./manifests/
COPY migrations/ ./migrations/

EXPOSE 8200

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200", "--workers", "2"]
