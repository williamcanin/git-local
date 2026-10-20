"""make install: the steps in order. Each step lives in its own module."""

from __future__ import annotations

import os
import pathlib
import subprocess
import time

from .config import count_users, prepare_config, update_root_url
from .network import address_from_network, check_mdns_conflict, warn_lan_ports
from .paths import DUMP_TIMER, MDNS_UNIT, ROOT_RECORD, USER_UNIT, Layout
from .sshclient import configure_ssh_client, remove_legacy_gitea_key
from .state import State
from .system import (
    check_hosts,
    check_requirements,
    check_root,
    create_directories,
    disable_legacy_unit,
    install_custom_files,
    enable_avahi,
    enable_linger,
    install_etc_files,
    reload_nginx,
    require_arch,
)
from .units import install_dump_script, install_user_units
from .util import die, log, run, systemctl_user, warn


def choose_flavor(state: State) -> None:
    print("\nSelect the Git server to install:")
    print("  [1] Forgejo [Default]")
    print("  [2] Gitea")
    choice = input("Option [1]: ").strip() or "1"
    if choice == "1":
        state.flavor = "forgejo"
    elif choice == "2":
        state.flavor = "gitea"
    else:
        die(f"Invalid option: {choice}")
    log(f"Selected: {state.flavor}")


def choose_root(state: State) -> None:
    """The mount point that holds the data. There is no default."""
    answer = os.environ.get("GIT_LOCAL_ROOT", "").strip()
    if not answer:
        answer = input("Absolute path of the mount point that will hold the Git Local data: ").strip()
    if not answer:
        die("A mount point is required.")
    if not answer.startswith("/"):
        die(f"The mount point must be an absolute path: {answer}")
    if any(char in answer for char in "|&\\"):
        die(f"The mount point cannot contain |, & or \\: {answer}")
    answer = answer.rstrip("/")
    if not answer:
        die("The mount point cannot be /.")
    if not pathlib.Path(answer).is_mount():
        die(f"{answer} is not mounted. Mount it first, then run make install again.")
    state.layout = Layout(pathlib.Path(answer))
    log(f"Data root: {answer} (the data goes to {state.layout.base})")


def write_flavor_file(layout: Layout, state: State) -> None:
    layout.flavor_file.write_text(state.flavor + "\n")
    log(f"Recorded flavor in {layout.flavor_file}")


def write_root_record(layout: Layout) -> None:
    ROOT_RECORD.parent.mkdir(parents=True, exist_ok=True)
    ROOT_RECORD.write_text(str(layout.root) + "\n")
    log(f"Recorded data root in {ROOT_RECORD}")


def create_admin(layout: Layout, state: State) -> None:
    """Run migrations and create the first administrator from the terminal."""
    run([state.flavor, "migrate", "--config", str(layout.config)])
    if count_users(layout.db) > 0:
        log("An administrator already exists; skipping account creation")
        return

    username = input("Administrator username: ").strip()
    email = input("Administrator email: ").strip()
    if not username or not email:
        die("Username and email are required.")

    log(f"Creating administrator '{username}'. The random password is printed once; it must be changed at first login.")
    run([state.flavor, "admin", "user", "create", "--admin", "--username", username, "--email", email,
         "--random-password", "--must-change-password", "--config", str(layout.config)])


def start_services(state: State) -> None:
    log("Enabling the daily dump timer")
    systemctl_user("enable", "--now", DUMP_TIMER)

    log(f"Enabling and starting {MDNS_UNIT}")
    systemctl_user("enable", "--now", MDNS_UNIT)
    time.sleep(2)
    check_mdns_conflict(state)

    if not state.fstab_ok:
        warn(f"{USER_UNIT} was not started because {state.layout.root} is not in /etc/fstab.")
        return
    log(f"Enabling and starting {USER_UNIT}")
    systemctl_user("enable", "--now", USER_UNIT)


def cmd_install() -> None:
    state = State()
    require_arch()
    choose_flavor(state)
    choose_root(state)
    check_requirements(state)
    check_hosts()
    address_from_network(state)
    check_root(state)
    assert state.layout is not None
    layout = state.layout

    create_directories(layout)
    install_custom_files(layout)
    prepare_config(layout, state.flavor, state.lan_ip)
    update_root_url(layout, state.lan_ip)
    write_flavor_file(layout, state)
    write_root_record(layout)
    install_etc_files()
    install_user_units(state.flavor, layout, state.lan_ip)
    install_dump_script(layout)
    disable_legacy_unit()
    enable_linger()
    enable_avahi()
    warn_lan_ports(state)
    try:
        reload_nginx()
    except subprocess.CalledProcessError as error:
        warn(f"nginx was not reloaded: {error}")
    remove_legacy_gitea_key()
    configure_ssh_client()
    create_admin(layout, state)
    start_services(state)
    log("Done. Open http://git.local and sign in with the administrator account.")
