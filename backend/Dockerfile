# Use a standard Python slim image
FROM python:3.11-slim

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/ /usr/local/bin/

WORKDIR /workspace

# Copy files
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend
COPY db/ ./db

# Sync dependencies using uv (without installing the project as a package)
RUN uv pip install --system -r pyproject.toml

# Expose port
EXPOSE 8000

# Set environment variables
ENV DATABASE_URL="postgresql://postgres@localhost/mockingbird"
ENV HOST="0.0.0.0"
ENV PORT="8000"

# Command to run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
