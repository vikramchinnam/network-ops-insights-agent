# Network Ops Insights chat app
# Build for Snowpark Container Services (linux/amd64):
#   docker build --platform linux/amd64 -t noi_app:v1 spcs
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencies first, so code changes don't reinstall them (faster rebuilds)
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Never run as root
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
