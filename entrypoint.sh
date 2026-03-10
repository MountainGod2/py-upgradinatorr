#!/bin/sh
set -eu

PUID="${PUID:-999}"
PGID="${PGID:-999}"

CHOWN_CONFIG_RECURSIVE="${CHOWN_CONFIG_RECURSIVE:-0}"
SEED_CONFIG="${SEED_CONFIG:-1}"

CONFIG_PATH="${CONFIG_PATH:-/config/upgradinatorr.conf}"
EXAMPLE_CONFIG_PATH="${EXAMPLE_CONFIG_PATH:-/app/upgradinatorr-example.conf}"

APP_COMMAND="${APP_COMMAND:-upgradinatorr}"

XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp/.cache}"

export XDG_CACHE_HOME

mkdir -p /config
mkdir -p "${XDG_CACHE_HOME}"

chown "${PUID}:${PGID}" /config 2>/dev/null || true
chown -R "${PUID}:${PGID}" "${XDG_CACHE_HOME}" 2>/dev/null || true

if [ "${CHOWN_CONFIG_RECURSIVE}" = "1" ]; then
  echo "CHOWN_CONFIG_RECURSIVE=1: chowning /config recursively to ${PUID}:${PGID}"
  chown -R "${PUID}:${PGID}" /config 2>/dev/null || true
else
  if find /config -mindepth 1 -maxdepth 1 -user 0 2>/dev/null | grep -q .; then
    echo "Fixing top-level root-owned entries in /config to ${PUID}:${PGID}"
    find /config -mindepth 1 -maxdepth 1 -user 0 -exec chown "${PUID}:${PGID}" {} + 2>/dev/null || true
  fi
fi

if [ "${SEED_CONFIG}" = "1" ]; then
  if [ ! -f "${CONFIG_PATH}" ] && [ -f "${EXAMPLE_CONFIG_PATH}" ]; then
    echo "Seeding default config: ${CONFIG_PATH}"
    cp "${EXAMPLE_CONFIG_PATH}" "${CONFIG_PATH}"
    chown "${PUID}:${PGID}" "${CONFIG_PATH}" 2>/dev/null || true
  fi
fi

exec gosu "${PUID}:${PGID}" ${APP_COMMAND} "$@"