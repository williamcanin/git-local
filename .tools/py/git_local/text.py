"""Pure text helpers: no system access, so they are easy to test."""

from __future__ import annotations

import datetime as dt
import re
from typing import Iterable, Optional

from .paths import STAMP_FORMAT

BACKUP_SUFFIX = re.compile(r"\.bak-(\d{2}-\d{2}-\d{4}_\d{2}-\d{2}-\d{2})$")


def backup_name(path: str, when: str) -> str:
    return f"{path}.bak-{when}"


def latest_backup(names: Iterable[str]) -> Optional[str]:
    """Newest backup name, sorted by the timestamp in the name (not by mtime)."""
    best: Optional[str] = None
    best_time: Optional[dt.datetime] = None
    for name in names:
        match = BACKUP_SUFFIX.search(name)
        if not match:
            continue
        when = dt.datetime.strptime(match.group(1), STAMP_FORMAT)
        if best_time is None or when > best_time:
            best, best_time = name, when
    return best


def fstab_has_mount(fstab_text: str, root: str) -> bool:
    for line in fstab_text.splitlines():
        fields = line.split()
        if fields and not fields[0].startswith("#") and len(fields) >= 2 and fields[1] == root:
            return True
    return False


def hosts_address(hosts_text: str, host: str) -> Optional[str]:
    for line in hosts_text.splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) >= 2 and host in fields[1:]:
            return fields[0]
    return None


def render_unit(text: str, root: str, lan_ip: str) -> str:
    return text.replace("@ROOT@", root).replace("@IP@", lan_ip)


def remove_legacy_gitea_lines(text: str) -> tuple[str, bool]:
    """Drop the key lines the old Gitea wrote to authorized_keys."""
    kept = [
        line
        for line in text.splitlines(keepends=True)
        if not line.startswith("# gitea public key") and not line.startswith('command="/usr/bin/gitea ')
    ]
    updated = "".join(kept)
    return updated, updated != text


def files_to_prune(entries: list[tuple[float, str]], keep: int) -> list[str]:
    """Names to delete, keeping the newest `keep` (entries are (mtime, name))."""
    ordered = sorted(entries, key=lambda item: item[0], reverse=True)
    return [name for _, name in ordered[keep:]]
