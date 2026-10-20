"""Output, command execution and backups. The only module that runs commands."""

from __future__ import annotations

import datetime as dt
import grp
import os
import pathlib
import pwd
import subprocess
import sys
from typing import Optional

from .paths import STAMP_FORMAT
from .text import backup_name


class Fatal(Exception):
    """Stop with a message and exit status 1."""


def log(message: str) -> None:
    print(f"==> {message}")


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def die(message: str) -> None:
    raise Fatal(message)


def stamp() -> str:
    return dt.datetime.now().strftime(STAMP_FORMAT)


def run(
    cmd: list[str],
    *,
    root: bool = False,
    check: bool = True,
    capture: bool = False,
    stdin_text: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Run a command, through sudo when root is needed and we are not root."""
    if root and os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    return subprocess.run(cmd, check=check, text=True, capture_output=capture, input=stdin_text)


def output(cmd: list[str]) -> str:
    """Stdout of a command, or an empty string when it fails."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def succeeds(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, check=False).returncode == 0
    except FileNotFoundError:
        return False


def systemctl_user(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(["systemctl", "--user", *args], check=check)


def user_unit_active(unit: str) -> bool:
    return succeeds(["systemctl", "--user", "is-active", "--quiet", unit])


def system_unit_active(unit: str) -> bool:
    return succeeds(["systemctl", "is-active", "--quiet", unit])


def current_user() -> tuple[str, str]:
    return pwd.getpwuid(os.getuid()).pw_name, grp.getgrgid(os.getgid()).gr_name


def linger_enabled(user: str) -> bool:
    return output(["loginctl", "show-user", user, "--property=Linger", "--value"]) == "yes"


def backup_file(path: pathlib.Path, privileged: bool = False) -> None:
    """Copy an existing file to <file>.bak-MM-DD-YYYY_HH-MM-SS (never overwrites)."""
    if path.exists() or path.is_symlink():
        backup = backup_name(str(path), stamp())
        log(f"Backing up {path} -> {backup}")
        run(["cp", "-a", "--", str(path), backup], root=privileged)
