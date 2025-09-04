# Use Python 3.12 slim image
FROM python:3.12-slim

# Install system dependencies needed for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgthread-2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /app

# Install the application dependencies.
WORKDIR /app
# Since we're using a non-standard project structure with the backend in a subdirectory
# but pyproject.toml in the root, we need to set PYTHONPATH
ENV PYTHONPATH=/app

RUN uv sync --frozen --no-cache

# Add the virtual environment to PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Create necessary directories
RUN mkdir -p /app/static/uploads /app/static/images /app/static/videos
RUN mkdir -p /app/backend/static/uploads /app/backend/static/images /app/backend/static/videos

# Verify the fastapi command is available
RUN ls -la /app/.venv/bin/ && /app/.venv/bin/fastapi --version

# Expose port
EXPOSE 80

# Run the application using fastapi CLI with a shell wrapper to ensure PATH is set
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["exec /app/.venv/bin/fastapi run backend/main.py --port 80 --host 0.0.0.0"] 