FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

# Install dependencies first so Docker can cache this layer when only the code changes.
COPY pyproject.toml .
COPY app app
RUN pip install .

COPY alembic.ini .
COPY alembic alembic

# Run as an unprivileged user.
RUN useradd --system --no-create-home reactor
USER reactor

EXPOSE 8000
# Apply migrations, then start a single Uvicorn worker (the server has one vCPU).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
