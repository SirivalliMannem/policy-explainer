# Build from the repository root so the image can import the shared package:
#   docker build -f agents/policy-explainer/Dockerfile .

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY agents/policy-explainer/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY agents/policy-explainer/ /app/
COPY shared/ /shared/

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
