# Stage 1: Builder
FROM dhi.io/python:3.14-debian12-dev@sha256:88a9e52c968c496d1412140ef98673c1f0d5c52938a06e230266c7bef7933332 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20250419~deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.17@sha256:10787c682e4184e4f290de1171fd4703dc63de99221f10fe1c99002ce7fa9acc /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Stage 2: Runtime
FROM dhi.io/python:3.14-debian12@sha256:472146b277e4033ed2e9814b25115c0ace004732f3a4d14e733ee9f520a4c651

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

VOLUME /config
WORKDIR /config

COPY --chmod=0755 entrypoint.py /entrypoint.py

ENTRYPOINT ["python", "/entrypoint.py"]
CMD ["--help"]

LABEL org.opencontainers.image.source="https://github.com/MountainGod2/py-upgradinatorr"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.authors="MountainGod2"
LABEL org.opencontainers.image.description="Upgradinatorr"