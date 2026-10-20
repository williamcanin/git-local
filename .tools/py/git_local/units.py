"""systemd user units and the dump script: rendering, installing and removing."""

from __future__ import annotations

import shutil

from .paths import (
    CLIENT_BIN_DIR,
    CLIENT_SCRIPT_SOURCE,
    DUMP_SERVICE,
    DUMP_SOURCE,
    DUMP_TIMER,
    MDNS_UNIT,
    SRC_DIR,
    USER_UNIT,
    USER_UNIT_DIR,
    Layout,
)
from .text import render_unit
from .util import backup_file, log, systemctl_user


def install_user_file(src, dest, root: str, lan_ip: str) -> None:
    """Render @ROOT@ and @IP@ placeholders, back up the old file, write the new one."""
    rendered = render_unit(src.read_text(), root, lan_ip)
    backup_file(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rendered)
    dest.chmod(0o644)
    log(f"Installed {dest}")


def install_user_units(flavor: str, layout: Layout, lan_ip: str) -> None:
    USER_UNIT_DIR.mkdir(parents=True, exist_ok=True)
    units_dir = SRC_DIR / ".config" / "systemd" / "user"
    install_user_file(units_dir / flavor / "git-local.service", USER_UNIT_DIR / USER_UNIT, str(layout.root), lan_ip)
    for name in [DUMP_SERVICE, DUMP_TIMER, MDNS_UNIT]:
        install_user_file(units_dir / name, USER_UNIT_DIR / name, str(layout.root), lan_ip)
    systemctl_user("daemon-reload")


def remove_user_units() -> None:
    log(f"Removing user units from {USER_UNIT_DIR}")
    for name in [USER_UNIT, DUMP_SERVICE, DUMP_TIMER, MDNS_UNIT]:
        (USER_UNIT_DIR / name).unlink(missing_ok=True)
    systemctl_user("daemon-reload")


def install_dump_script(layout: Layout) -> None:
    """Copy the standalone dump script into the data root (it runs without this project)."""
    log(f"Installing dump script: {layout.dump_script}")
    shutil.copy2(DUMP_SOURCE, layout.dump_script)
    layout.dump_script.chmod(0o755)


def remove_dump_script(layout: Layout) -> None:
    if layout.dump_script.exists():
        log(f"Removing {layout.dump_script}")
        layout.dump_script.unlink()
    try:
        (layout.base / "bin").rmdir()
    except OSError:
        pass


def install_client_script() -> None:
    """Install the git.local client script in ~/.local/bin, replacing any existing copy."""
    dest = CLIENT_BIN_DIR / "git.local"
    CLIENT_BIN_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CLIENT_SCRIPT_SOURCE, dest)
    dest.chmod(0o755)
    log(f"Installed {dest}")
