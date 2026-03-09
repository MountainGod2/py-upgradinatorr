FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends gosu curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && gosu nobody true

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app

ARG EXAMPLE_CONFIG_URL="https://raw.githubusercontent.com/angrycuban13/Just-A-Bunch-Of-Starr-Scripts/refs/heads/main/Upgradinatorr/upgradinatorr-example.conf"
ARG EXAMPLE_CONFIG_CHECKSUM="690030280b5fb21b16f991a14dd8b6e257ea72e907ee4e11b0973e85a77d2b4c"
RUN curl -sL "${EXAMPLE_CONFIG_URL}" -o /app/upgradinatorr-example.conf \
 && echo "${EXAMPLE_CONFIG_CHECKSUM}  /app/upgradinatorr-example.conf" | sha256sum -c -

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PUID=999
ENV PGID=999

ENV UV_CACHE_DIR=/config/.cache/uv
ENV XDG_CACHE_HOME=/config/.cache

RUN mkdir -p /config
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