FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV BIBTEX_UI_DIR=/app/docs

WORKDIR /app

RUN addgroup --system verifier \
    && adduser --system \
        --ingroup verifier \
        verifier

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY docs ./docs

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER verifier

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=10s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD [
    "uvicorn",
    "bibtex_verifier.api:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000"
]