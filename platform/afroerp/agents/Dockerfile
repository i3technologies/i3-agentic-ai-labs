FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY afroerp_agent.py .
RUN useradd -m -u 1001 agent && chown -R agent /app
USER agent
EXPOSE 8080
CMD ["uvicorn", "afroerp_agent:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
