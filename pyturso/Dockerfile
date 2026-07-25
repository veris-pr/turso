# Dev/test environment for pyturso (the Python port of Turso).
# Python 3.11+ toolchain only: stdlib runtime + pytest/mypy for dev.
# No Rust toolchain here — pyturso is Python-only; the Rust tree under core/
# is reference material read from the host, not built in this image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dev toolchain pinned by pyproject.toml [project.optional-dependencies].dev.
RUN pip install --no-cache-dir "pytest>=8" "mypy>=1.10"

WORKDIR /workspace/pyturso

# Container is kept alive by docker-compose (sleep infinity); all commands
# run via `docker compose exec` so the host toolchain is never touched.
CMD ["sleep", "infinity"]
