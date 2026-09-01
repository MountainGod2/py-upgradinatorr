# Stage 1: Builder
FROM dhi.io/python:3.14-debian12-dev AS builder

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.8@sha256:d1cbaeadc234fe19c0d93daabcf5e98738cd93c6d1dd4918ef6aa30735feb23a /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Stage 2: Runtime
FROM dhi.io/python:3.14-debian12

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

VOLUME /config
WORKDIR /config

COPY --chmod=0755 entrypoint.py /entrypoint.py

ENTRYPOINT ["python", "/entrypoint.py"]
CMD ["--help"]

LABEL org.opencontainers.image.source="https://github.com/MountainGod2/upgradinatorr"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.authors="MountainGod2"
LABEL org.opencontainers.image.description="Upgradinatorr"