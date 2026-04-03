# Clarvis — contributor quickstart container
# NOT for production (production runs systemd-native, see AGENTS.md)
#
# Usage:
#   docker compose up --build
#   docker compose run clarvis clarvis demo
#   docker compose run clarvis clarvis brain health
#   docker compose run clarvis pytest -m "not slow"

FROM python:3.12-slim AS base

# System deps for ChromaDB / ONNX / SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        sqlite3 \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install main package with brain + dev extras (spine provides all runtime functionality)
COPY pyproject.toml README.md LICENSE ./
COPY clarvis/ clarvis/
COPY tests/ tests/
RUN pip install --no-cache-dir ".[all]"

# Copy deprecated packages (tests only, not runtime dependencies)
COPY packages/ packages/

# Copy scripts (needed by tests and CLI)
COPY scripts/ scripts/

# Set workspace root so brain finds data dirs
ENV CLARVIS_WORKSPACE=/app
ENV CLARVIS_GRAPH_BACKEND=sqlite

# Create data directories (brain auto-creates, but be explicit)
RUN mkdir -p data/clarvisdb data/clarvisdb-local

# Smoke test: CLI loads without error
RUN clarvis --help

# Default: run the self-contained demo
CMD ["clarvis", "demo"]
