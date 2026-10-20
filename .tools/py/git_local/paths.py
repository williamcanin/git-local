"""Constants and the data-root layout shared by every module."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

# .tools/py/git_local/paths.py -> project root
PROJECT_DIR = pathlib.Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_DIR / "src"
DUMP_SOURCE = PROJECT_DIR / ".tools" / "py" / "dump.py"

HOME = pathlib.Path.home()
ROOT_RECORD = HOME / ".config" / "git-local" / "root"
CLIENT_BIN_DIR = HOME / ".local" / "bin"
CLIENT_SCRIPT_SOURCE = PROJECT_DIR / "src" / ".local" / "bin" / "git.local"
USER_UNIT_DIR = HOME / ".config" / "systemd" / "user"
SSH_CONFIG = HOME / ".ssh" / "config"
AUTHORIZED_KEYS = HOME / ".ssh" / "authorized_keys"
HOSTS_FILE = pathlib.Path("/etc/hosts")
FSTAB_FILE = pathlib.Path("/etc/fstab")
ETC_DIR = pathlib.Path("/etc")

HTTP_PORT = 3000
LAN_PORT = 8080
SSH_PORT = 2222
KEEP_DUMPS = 7

USER_UNIT = "git-local.service"
DUMP_SERVICE = "git-local-dump.service"
DUMP_TIMER = "git-local-dump.timer"
MDNS_UNIT = "git-local-mdns.service"
LEGACY_UNIT = "gitea.service"

SSH_CLIENT_HOST = "local"
SSH_USER = "git"
GIT_HOST = "git.local"
STAMP_FORMAT = "%m-%d-%Y_%H-%M-%S"

FLAVORS = {
    "forgejo": ["forgejo", "forgejo-cli"],
    "gitea": ["gitea", "gitea-runner"],
}
BASE_PACKAGES = ["unzip", "nginx", "avahi"]

FSTAB_HINT = "UUID=<uuid-of-the-drive> {root} exfat uid={user},gid={group} dmask=007,fmask=007,nofail,x-gvfs-show 0 0"


@dataclass
class Layout:
    """Every path that depends on the data root."""

    root: pathlib.Path

    @property
    def base(self) -> pathlib.Path:
        return self.root / "git.local"

    @property
    def config(self) -> pathlib.Path:
        return self.base / "config" / "config.ini"

    @property
    def flavor_file(self) -> pathlib.Path:
        return self.base / "config" / "flavor"

    @property
    def db(self) -> pathlib.Path:
        return self.base / "data" / "git-local.db"

    @property
    def dump_script(self) -> pathlib.Path:
        return self.base / "bin" / "dump.py"

    @property
    def backup(self) -> pathlib.Path:
        return self.base / "backup"
