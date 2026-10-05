# Stage 1: Builder
FROM dhi.io/python:3.14-debian12-dev@sha256:4b3a77c1aa89e623fc9d19ff5f9a13ea5482346b64befeef2acd7e1f0206da5f AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20250419~deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 /uv /uvx /bin/

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
FROM dhi.io/python:3.14-debian12@sha256:fea7f29d0d72e87f7de2a2909acf7fc5057da58a9f9ab6cbcdcdef9cefae9959

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