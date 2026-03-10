FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends gosu ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 999 upgradinatorr \
 && useradd --system --gid 999 --uid 999 --create-home upgradinatorr

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

ENV PATH="/app/.venv/bin:$PATH"
ENV PUID=999
ENV PGID=999

ENV XDG_CACHE_HOME=/tmp/.cache

RUN mkdir -p /config \
 && chown 999:999 /config
VOLUME /config
WORKDIR /config

COPY entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]

LABEL org.opencontainers.image.source="https://github.com/MountainGod2/upgradinatorr"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.authors="MountainGod2"
LABEL org.opencontainers.image.description="Upgradinatorr"