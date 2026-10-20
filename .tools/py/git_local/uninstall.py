"""make uninstall, make status and make check-ssh."""

from __future__ import annotations

from .paths import DUMP_SERVICE, DUMP_TIMER, MDNS_UNIT, ROOT_RECORD, SSH_CONFIG, SSH_PORT, USER_UNIT
from .sshclient import check_ssh_config
from .state import load_root
from .system import restore_etc_files
from .units import remove_dump_script, remove_user_units
from .util import current_user, linger_enabled, log, run, systemctl_user


def confirm(question: str) -> bool:
    return input(f"{question} [y/N] ").strip().lower() in {"y", "yes"}


def cmd_uninstall() -> None:
    layout = load_root()
    if not confirm("Remove the Git Local services, nginx files and dump script? Data in " + str(layout.base) + " is kept."):
        log("Cancelled.")
        return

    log("Stopping and disabling the service, the dump timer and the announcement")
    systemctl_user("disable", "--now", MDNS_UNIT, DUMP_TIMER, DUMP_SERVICE, USER_UNIT, check=False)

    remove_user_units()
    restore_etc_files(str(layout.root), "")
    remove_dump_script(layout)

    if ROOT_RECORD.exists():
        ROOT_RECORD.unlink()
        try:
            ROOT_RECORD.parent.rmdir()
        except OSError:
            pass

    user, _ = current_user()
    if linger_enabled(user):
        log(f"Disabling linger for {user}")
        run(["loginctl", "disable-linger", user], root=True)

    log(f"Uninstall complete. Kept: {layout.base} (data, config, log, backup), installed packages, ~/.ssh files, and the Port {SSH_PORT} line in {SSH_CONFIG}.")


def cmd_status() -> None:
    layout = load_root()
    systemctl_user("status", USER_UNIT, "--no-pager", check=False)
    systemctl_user("list-timers", DUMP_TIMER, "--no-pager", check=False)
    systemctl_user("status", MDNS_UNIT, "--no-pager", check=False)
    run(["nginx", "-t"], root=True, check=False)
    check_ssh_config()
    log(f"Data root: {layout.root}")


def cmd_check_ssh() -> None:
    if not check_ssh_config():
        raise SystemExit(1)
