###############################################
# Base stage (shared between build and final) #
###############################################

FROM python:3.13-slim AS base

###############
# Build stage #
###############

FROM base AS builder

## Install and configure UV, see https://docs.astral.sh/uv/ for more information

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY uv.lock pyproject.toml /app/
RUN uv sync \
    --frozen \
    --no-dev \
    --no-install-workspace \
    --no-editable \
    --all-packages

COPY *.py *.md /app/
COPY backend /app/backend

###############
# Final image #
###############

FROM base

RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0

RUN groupadd -r app
RUN useradd -r -d /app -g app -N app

COPY --from=builder --chown=app:app /app /app
WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Expose the application port
EXPOSE 80
WORKDIR /app

CMD [".venv/bin/python", "backend/main.py"]