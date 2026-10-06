FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY handler.py .
EXPOSE 8000
USER 1001
CMD ["uvicorn", "handler:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
