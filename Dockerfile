FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN mkdir -p /data

ENV DATABASE_URL=sqlite+aiosqlite:////data/autoparts.db

EXPOSE 8080

CMD ["python", "-m", "app.main"]
