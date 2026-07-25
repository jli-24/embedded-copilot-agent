FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY knowledge ./knowledge
COPY web ./web
COPY demo ./demo

RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir --no-deps .

EXPOSE 8000 8501

CMD ["python", "-m", "uvicorn", "embedded_copilot.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
