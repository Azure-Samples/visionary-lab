# Keep the runtime aligned with requires-python = ">=3.13" in pyproject.toml.
FROM python:3.13-slim

# Install system dependencies needed for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgthread-2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV PYTHONPATH=/app

# Install dependencies in a cacheable layer before copying application code.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-install-project

# Copy only the backend runtime after dependencies are resolved.
COPY backend ./backend

# Add the virtual environment to PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Create necessary directories
RUN mkdir -p /app/static/uploads /app/static/images /app/static/videos
RUN mkdir -p /app/backend/static/uploads /app/backend/static/images /app/backend/static/videos

# Verify the fastapi command is available
RUN ls -la /app/.venv/bin/ && /app/.venv/bin/fastapi --version

# Expose port
EXPOSE 80

# The same immutable image runs either the API or a queue worker. Container Apps
# sets IMAGE_JOB_ROLE per app, so no HTTP server is started in worker replicas.
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["if [ \"${IMAGE_JOB_ROLE:-api}\" = \"worker\" ]; then exec /app/.venv/bin/python -m backend.worker; else exec /app/.venv/bin/fastapi run backend/main.py --port 80 --host 0.0.0.0; fi"]
