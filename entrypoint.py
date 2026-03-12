#!/usr/bin/env python
"""Docker entrypoint script for upgradinatorr.

This script handles container initialization including:
- Setting up user permissions (PUID/PGID)
- Creating and managing configuration directories
- Seeding configuration files
- Dropping privileges and executing the application
"""

import contextlib
import os
import pathlib
import shutil
import subprocess
import sys


def safe_chown(
    path: str | os.PathLike[str], uid: int, gid: int, *, recursive: bool = False
) -> None:
    """Safely change ownership of a path, suppressing errors.

    Args:
        path: Path to change ownership of.
        uid: User ID to set.
        gid: Group ID to set.
        recursive: Whether to recursively change ownership. Defaults to False.
    """
    path_obj = pathlib.Path(path)
    with contextlib.suppress(OSError):
        os.chown(path_obj, uid, gid)

    if recursive:
        try:
            for root, dirs, files in os.walk(path_obj):
                for d in dirs:
                    with contextlib.suppress(OSError):
                        os.chown(pathlib.Path(root) / d, uid, gid)
                for f in files:
                    with contextlib.suppress(OSError):
                        os.chown(pathlib.Path(root) / f, uid, gid)
        except OSError:
            pass


def main() -> None:
    """Execute the entrypoint logic for the Docker container.

    Sets up the environment, manages permissions, and executes the application
    with appropriate privileges.
    """
    try:
        puid = int(os.environ.get("PUID", "999"))
    except ValueError:
        puid = 999

    try:
        pgid = int(os.environ.get("PGID", "999"))
    except ValueError:
        pgid = 999

    chown_config_recursive = os.environ.get("CHOWN_CONFIG_RECURSIVE", "0") == "1"
    seed_config = os.environ.get("SEED_CONFIG", "1") == "1"

    config_path = os.environ.get("CONFIG_PATH", "/config/upgradinatorr.conf")
    example_config_path = os.environ.get("EXAMPLE_CONFIG_PATH", "/app/upgradinatorr-example.conf")
    app_command = os.environ.get("APP_COMMAND", "upgradinatorr")
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME", "/tmp/.cache")  # noqa: S108

    os.environ["XDG_CACHE_HOME"] = xdg_cache_home

    pathlib.Path("/config").mkdir(exist_ok=True, parents=True)
    pathlib.Path(xdg_cache_home).mkdir(exist_ok=True, parents=True)

    safe_chown("/config", puid, pgid)
    safe_chown(xdg_cache_home, puid, pgid, recursive=True)

    if chown_config_recursive:
        safe_chown("/config", puid, pgid, recursive=True)
    else:
        with contextlib.suppress(OSError):
            config_dir = pathlib.Path("/config")
            for entry in config_dir.iterdir():
                try:
                    s = entry.stat()
                    if s.st_uid == 0:
                        os.chown(entry, puid, pgid)
                except OSError:
                    pass

    if (
        seed_config
        and not pathlib.Path(config_path).exists()
        and pathlib.Path(example_config_path).exists()
    ):
        with contextlib.suppress(OSError):
            shutil.copy2(example_config_path, config_path)
            os.chown(config_path, puid, pgid)

    # Drop privileges by switching to pgid then puid
    if hasattr(os, "setgid") and hasattr(os, "setuid"):
        with contextlib.suppress(OSError):
            os.setgroups([])  # Drop supplementary groups if any

        with contextlib.suppress(OSError):
            os.setgid(pgid)
        with contextlib.suppress(OSError):
            os.setuid(puid)

    # Exec application
    try:
        sys.stdout.flush()
        sys.stderr.flush()

        # We need to search the PATH for the command if it's not an absolute path
        cmd_path = shutil.which(app_command)
        if not cmd_path:
            cmd_path = app_command

        result = subprocess.run([cmd_path, *sys.argv[1:]], check=False)  # noqa: S603
        sys.exit(result.returncode)
    except OSError:
        sys.exit(1)


if __name__ == "__main__":
    main()
