FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first so this layer caches independently of app code.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Unprivileged runtime user. The evidence dir is created (and owned) here so
# a fresh named volume inherits app ownership.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app \
    && mkdir -p /app/data/evidence \
    && chown -R app:app /app/data \
    && chmod +x docker-entrypoint.sh

USER app

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
