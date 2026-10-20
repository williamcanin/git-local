"""Host checks and system changes: packages, /etc files, nginx, linger, avahi."""

from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tempfile

from .paths import BASE_PACKAGES, ETC_DIR, FLAVORS, FSTAB_FILE, FSTAB_HINT, GIT_HOST, HOSTS_FILE, LEGACY_UNIT, SRC_DIR, Layout
from .state import State
from .text import fstab_has_mount, hosts_address, latest_backup, mirror_paths, render_unit
from .util import (
    backup_file,
    current_user,
    linger_enabled,
    die,
    log,
    output,
    run,
    succeeds,
    system_unit_active,
    systemctl_user,
    warn,
)


def require_arch() -> None:
    if not pathlib.Path("/etc/arch-release").exists():
        die("This installer only supports Arch Linux.")


def check_hosts() -> None:
    """git.local must be in /etc/hosts on this computer (other computers use mDNS)."""
    address = hosts_address(HOSTS_FILE.read_text(), GIT_HOST)
    if address is None:
        warn(f"{GIT_HOST} is not in {HOSTS_FILE}. Add a line that maps it to this machine, then run make install again:")
        print(f"\n    127.0.0.1 {GIT_HOST}\n", file=sys.stderr)
        print("Use the address of this machine instead of 127.0.0.1 if other computers on the network will access it.\n", file=sys.stderr)
        raise SystemExit(1)
    log(f"{GIT_HOST} resolves to {address} in {HOSTS_FILE}")


def check_requirements(state: State) -> None:
    """Report missing packages; the installer never installs them."""
    required = BASE_PACKAGES + FLAVORS[state.flavor]
    missing = [pkg for pkg in required if not succeeds(["pacman", "-Q", pkg])]
    if missing:
        warn(f"Missing packages: {' '.join(missing)}")
        print(f"\nInstall them manually, then run make install again:\n\n    sudo pacman -S --needed {' '.join(missing)}\n", file=sys.stderr)
        raise SystemExit(1)
    log("All required packages are installed")


def check_root(state: State) -> None:
    """The data root must be mounted, and should have an /etc/fstab entry for boot."""
    assert state.layout is not None
    root = str(state.layout.root)
    if not pathlib.Path(root).is_mount():
        die(f"{root} is not mounted. Mount it first.")
    log(f"{root} is mounted")
    if not fstab_has_mount(FSTAB_FILE.read_text(), root):
        state.fstab_ok = False
        user, group = current_user()
        warn(f"/etc/fstab has no entry for {root}. Add this line (replace the UUID with the drive's UUID, see 'lsblk -o UUID,MOUNTPOINT'), run 'sudo systemctl daemon-reload' and then 'make install' again:")
        print(f"\n    {FSTAB_HINT.format(root=root, user=user, group=group)}\n", file=sys.stderr)


def create_directories(layout: Layout) -> None:
    log(f"Creating directories under {layout.base}")
    for sub in ["config", "data/lfs", "data/repositories", "log", "backup", "bin"]:
        (layout.base / sub).mkdir(parents=True, exist_ok=True)


def install_custom_files(layout: Layout) -> None:
    """Copy src/custom (theme, logo, favicon) to <root>/git.local/custom, backing up replaced files.

    Forgejo reads files under custom/public/ in place of its built-in ones.
    """
    for src, dest in mirror_paths(SRC_DIR / "custom", layout.base / "custom"):
        dest.parent.mkdir(parents=True, exist_ok=True)
        backup_file(dest)
        shutil.copy2(src, dest)
        log(f"Installed {dest}")


def etc_files() -> list[pathlib.Path]:
    """Files under src/etc, which are copied to the same paths under /etc."""
    return sorted(path for path in (SRC_DIR / "etc").rglob("*") if path.is_file())


CERT_FILES = ("git.local.pem", "git.local-key.pem")


def rendered_etc(src: pathlib.Path, root: str, lan_ip: str) -> str:
    """Content of a src/etc file with @ROOT@ and @IP@ replaced."""
    return render_unit(src.read_text(), root, lan_ip)


def install_cert_files(layout: Layout) -> bool:
    """Copy src/cert/*.pem to <root>/git.local/cert. The private key is never in git.

    Returns False (and warns) when a file is missing; nginx then cannot start HTTPS.
    """
    source = SRC_DIR / "cert"
    cert_dir = layout.base / "cert"
    missing = [name for name in CERT_FILES if not (source / name).exists()]
    if missing:
        warn(f"Missing certificate file(s) in {source}: {', '.join(missing)}. HTTPS will not start until they are in {cert_dir}.")
        return False

    cert_dir.mkdir(parents=True, exist_ok=True)
    for name in CERT_FILES:
        dest = cert_dir / name
        backup_file(dest)
        shutil.copy2(source / name, dest)
        dest.chmod(0o600 if name.endswith("-key.pem") else 0o644)
        log(f"Installed {dest}")
    return True


def install_etc_files(layout: Layout, lan_ip: str) -> None:
    """Copy src/etc/** to /etc/**, rendering placeholders and backing up what it replaces."""
    for src in etc_files():
        dest = ETC_DIR / src.relative_to(SRC_DIR / "etc")
        handle, tmp_name = tempfile.mkstemp()
        with os.fdopen(handle, "w") as tmp:
            tmp.write(rendered_etc(src, str(layout.root), lan_ip))
        backup_file(dest, privileged=True)
        run(["install", "-D", "-m", "644", tmp_name, str(dest)], root=True)
        os.unlink(tmp_name)
        log(f"Installed {dest}")


def restore_etc_files(root: str, lan_ip: str) -> None:
    """Undo install_etc_files: restore the newest backup, or remove a file the install created."""
    for src in etc_files():
        dest = ETC_DIR / src.relative_to(SRC_DIR / "etc")
        backup = latest_backup(str(path) for path in dest.parent.glob(dest.name + ".bak-*"))
        if backup:
            run(["cp", "-a", "--", backup, str(dest)], root=True)
            log(f"Restored {dest} from {backup}")
        elif dest.exists() and dest.read_text() == rendered_etc(src, root, lan_ip):
            run(["rm", "-f", "--", str(dest)], root=True)
            log(f"Removed {dest}")
        elif dest.exists():
            warn(f"{dest} differs from the installed copy and has no backup; left in place.")

    if run(["nginx", "-t"], root=True, check=False).returncode == 0:
        if system_unit_active("nginx"):
            run(["systemctl", "reload", "nginx"], root=True)
    else:
        warn("nginx configuration test failed after restoring /etc files; nginx was not reloaded.")


def reload_nginx() -> None:
    log("Testing nginx configuration")
    if run(["nginx", "-t"], root=True, check=False).returncode != 0:
        warn("nginx configuration test failed; nginx was not reloaded.")
        return
    if system_unit_active("nginx"):
        run(["systemctl", "reload", "nginx"], root=True)
    else:
        run(["systemctl", "enable", "--now", "nginx"], root=True)


def enable_linger() -> None:
    """Linger lets user services start at boot without a login session."""
    user, _ = current_user()
    if linger_enabled(user):
        log(f"Linger already enabled for {user}")
    else:
        log(f"Enabling linger for {user}")
        run(["loginctl", "enable-linger", user], root=True)


def enable_avahi() -> None:
    """Avahi is a system service that announces names on the network (mDNS)."""
    if not system_unit_active("avahi-daemon"):
        log("Enabling avahi-daemon")
        run(["systemctl", "enable", "--now", "avahi-daemon"], root=True)


def disable_legacy_unit() -> None:
    """Gitea and Forgejo both use port 3000, so the old user unit must not run."""
    if succeeds(["systemctl", "--user", "cat", LEGACY_UNIT]):
        log(f"Disabling {LEGACY_UNIT} (its data is kept)")
        systemctl_user("disable", "--now", LEGACY_UNIT)
