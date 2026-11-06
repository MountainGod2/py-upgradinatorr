# Stage 1: Builder
FROM dhi.io/python:3.14-debian12-dev@sha256:d4144e9304ba3b66b20531852c4f4313ef64fee119be98b0cd5f5770230490cf AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20250419~deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /uvx /bin/

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
FROM dhi.io/python:3.14-debian12@sha256:a208c768414a353c9c1b6e246848e7e329db49266a0c21d601911ae71bf8d4c7

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