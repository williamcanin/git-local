"""The 'Host local' alias in ~/.ssh/config, and the legacy Gitea key in authorized_keys.

The pure functions work on text (CRLF-aware). The file is only edited, never created,
because it holds your own keys and hosts.
"""

from __future__ import annotations

import re
import sys

from .paths import AUTHORIZED_KEYS, SSH_CLIENT_HOST, SSH_CONFIG, SSH_PORT, SSH_USER
from .text import remove_legacy_gitea_lines
from .util import backup_file, log, warn


def ssh_block_span(lines: list[str], host: str) -> tuple[int, int] | None:
    """Indexes [start, end) of the 'Host <host>' block, or None."""
    start = None
    for index, raw in enumerate(lines):
        fields = raw.rstrip("\r").split()
        if fields and fields[0].lower() == "host":
            if start is not None:
                return start, index
            if len(fields) >= 2 and fields[1] == host:
                start = index
    return (start, len(lines)) if start is not None else None


def ssh_block_has(text: str, host: str, key: str, value: str) -> bool:
    lines = text.splitlines()
    span = ssh_block_span(lines, host)
    if span is None:
        return False
    for raw in lines[span[0] + 1 : span[1]]:
        fields = raw.rstrip("\r").split()
        if len(fields) >= 2 and fields[0].lower() == key.lower() and fields[1] == value:
            return True
    return False


def ssh_block_exists(text: str, host: str) -> bool:
    return ssh_block_span(text.splitlines(), host) is not None


def fix_ssh_block(text: str, host: str, port: int, user: str) -> tuple[str, list[str]]:
    """Set Port and User in the 'Host <host>' block. Returns the new text and what changed.

    Keeps the file's line endings (CRLF files stay CRLF). A missing block is not created.
    """
    if not ssh_block_exists(text, host):
        return text, []

    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    changes: list[str] = []

    if not ssh_block_has(text, host, "port", str(port)):
        span = ssh_block_span(lines, host)
        assert span is not None
        lines.insert(span[0] + 1, f"    Port {port}")
        changes.append(f"Port {port}")

    if not ssh_block_has(text, host, "user", user):
        span = ssh_block_span(lines, host)
        assert span is not None
        user_index = None
        for index in range(span[0] + 1, span[1]):
            if re.match(r"^\s*[Uu]ser\s", lines[index]):
                user_index = index
                break
        if user_index is not None:
            indent = re.match(r"^(\s*)", lines[user_index]).group(1)
            lines[user_index] = f"{indent}User {user}"
        else:
            lines.insert(span[0] + 1, f"    User {user}")
        changes.append(f"User {user}")

    return eol.join(lines), changes


def ssh_snippet(host: str, user: str, port: int) -> str:
    return (
        f"\n    Host {host}\n        HostName git.local\n        User {user}\n"
        f"        Port {port}\n        IdentityFile ~/.ssh/<your-key>\n        IdentitiesOnly yes\n"
    )


def configure_ssh_client() -> None:
    """Fix the 'local' block (port and user), then report its state."""
    if SSH_CONFIG.exists():
        text = SSH_CONFIG.read_text(newline="")
        updated, changes = fix_ssh_block(text, SSH_CLIENT_HOST, SSH_PORT, SSH_USER)
        if changes:
            backup_file(SSH_CONFIG)
            SSH_CONFIG.write_text(updated, newline="")
            for change in changes:
                log(f"Set {change} for host '{SSH_CLIENT_HOST}' in {SSH_CONFIG}")
    check_ssh_config()


def check_ssh_config() -> bool:
    """True when the 'local' block exists with the right port and user."""
    if not SSH_CONFIG.exists():
        warn(f"{SSH_CONFIG} does not exist. Create it with a '{SSH_CLIENT_HOST}' host block:")
        print(ssh_snippet(SSH_CLIENT_HOST, SSH_USER, SSH_PORT), file=sys.stderr)
        return False
    log(f"{SSH_CONFIG} exists")
    text = SSH_CONFIG.read_text()

    if not ssh_block_exists(text, SSH_CLIENT_HOST):
        warn(f"{SSH_CONFIG} has no 'Host {SSH_CLIENT_HOST}' block. Add this block:")
        print(ssh_snippet(SSH_CLIENT_HOST, SSH_USER, SSH_PORT), file=sys.stderr)
        return False
    log(f"'Host {SSH_CLIENT_HOST}' block found")

    if not ssh_block_has(text, SSH_CLIENT_HOST, "port", str(SSH_PORT)):
        warn(f"'Host {SSH_CLIENT_HOST}' has no 'Port {SSH_PORT}' line.")
        return False
    log(f"'Host {SSH_CLIENT_HOST}' uses port {SSH_PORT}")

    if not ssh_block_has(text, SSH_CLIENT_HOST, "user", SSH_USER):
        warn(f"'Host {SSH_CLIENT_HOST}' does not use 'User {SSH_USER}'.")
        return False
    log(f"'Host {SSH_CLIENT_HOST}' uses user {SSH_USER}")
    return True


def remove_legacy_gitea_key() -> None:
    """The old Gitea wrote its key to authorized_keys, pointing at its own database."""
    if not AUTHORIZED_KEYS.exists():
        return
    updated, changed = remove_legacy_gitea_lines(AUTHORIZED_KEYS.read_text())
    if not changed:
        return
    backup_file(AUTHORIZED_KEYS)
    AUTHORIZED_KEYS.write_text(updated)
    log(f"Removed the legacy Gitea key from {AUTHORIZED_KEYS}")
