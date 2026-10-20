"""Forgejo/Gitea configuration: template, ROOT_URL and the setup-safe rewrite."""

from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

from .paths import HTTP_PORT, LAN_PORT, SSH_PORT, SSH_USER, USER_UNIT, Layout
from .util import backup_file, die, log, run, stamp, systemctl_user, user_unit_active


def root_url(lan_ip: str) -> str:
    return f"http://{lan_ip}:{LAN_PORT}/"


def update_root_url_text(config_text: str, lan_ip: str) -> tuple[str, bool]:
    """Return the config with ROOT_URL set to the LAN address, and whether it changed."""
    wanted = f"ROOT_URL = {root_url(lan_ip)}"
    if wanted in config_text.splitlines():
        return config_text, False
    updated = re.sub(r"(?m)^ROOT_URL = .*$", wanted, config_text, count=1)
    return updated, updated != config_text


def has_line(text: str, line: str) -> bool:
    return line in text.splitlines()


def secret_names() -> list[str]:
    return ["SECRET_KEY", "INTERNAL_TOKEN", "JWT_SECRET", "LFS_JWT_SECRET"]


def config_text(
    base_dir: str,
    lan_ip: str,
    lfs_jwt_secret: str,
    secret_key: str,
    internal_token: str,
    jwt_secret: str,
) -> str:
    return f"""APP_NAME = Git Local
RUN_MODE = prod
RUN_USER = boss
WORK_PATH = {base_dir}

[actions]
ENABLED = false

[server]
DOMAIN = git.local
HTTP_ADDR = 127.0.0.1
HTTP_PORT = {HTTP_PORT}
ROOT_URL = {root_url(lan_ip)}
APP_DATA_PATH = {base_dir}/data
LFS_START_SERVER = true
LFS_JWT_SECRET = {lfs_jwt_secret}
DISABLE_SSH = false
START_SSH_SERVER = true
SSH_USER = {SSH_USER}
BUILTIN_SSH_SERVER_USER = {SSH_USER}
# Clone URLs show SSH_DOMAIN and SSH_PORT. Port 22 with USE_COMPAT_SSH_URI = false
# gives the short form "git@local:<owner>/<repo>.git"; USE_COMPAT_SSH_URI = true
# gives "ssh://git@local/<owner>/<repo>.git". Clients reach port {SSH_PORT}
# through the "local" host alias in ~/.ssh/config.
SSH_DOMAIN = local
SSH_LISTEN_PORT = {SSH_PORT}
SSH_PORT = 22
SSH_CREATE_AUTHORIZED_KEYS_FILE = false
SSH_AUTHORIZED_KEYS_BACKUP = false

[database]
DB_TYPE = sqlite3
PATH = {base_dir}/data/git-local.db

[repository]
ROOT = {base_dir}/data/repositories
USE_COMPAT_SSH_URI = false

[repository.pull-request]
DEFAULT_MERGE_STYLE = merge

[repository.signing]
DEFAULT_TRUST_MODEL = committer

[log]
MODE = console
LEVEL = info
ROOT_PATH = {base_dir}/log

[security]
INSTALL_LOCK = true
SECRET_KEY = {secret_key}
INTERNAL_TOKEN = {internal_token}
PASSWORD_HASH_ALGO = argon2

[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = true
REGISTER_EMAIL_CONFIRM = false
ENABLE_NOTIFY_MAIL = false
ALLOW_ONLY_EXTERNAL_REGISTRATION = false
ENABLE_CAPTCHA = false
DEFAULT_KEEP_EMAIL_PRIVATE = false
DEFAULT_ALLOW_CREATE_ORGANIZATION = true
DEFAULT_ENABLE_TIMETRACKING = true
NO_REPLY_ADDRESS = noreply.git.local

[session]
PROVIDER = file

[openid]
ENABLE_OPENID_SIGNIN = false
ENABLE_OPENID_SIGNUP = false

[mailer]
ENABLED = false

[cron.update_checker]
ENABLED = false

[oauth2]
JWT_SECRET = {jwt_secret}
"""


def count_users(db: Path) -> int:
    """Accounts in the database; 0 when the database or its schema does not exist yet."""
    if not db.exists():
        return 0
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return int(con.execute("SELECT COUNT(*) FROM user").fetchone()[0])
    except sqlite3.OperationalError:
        return 0
    finally:
        con.close()


def write_config(layout: Layout, flavor: str, lan_ip: str) -> None:
    log(f"Generating config: {layout.config}")
    secrets = {}
    for name in ["SECRET_KEY", "INTERNAL_TOKEN", "JWT_SECRET", "LFS_JWT_SECRET"]:
        secrets[name] = run([flavor, "generate", "secret", name], capture=True).stdout.strip()
    text = config_text(
        base_dir=str(layout.base),
        lan_ip=lan_ip,
        lfs_jwt_secret=secrets["LFS_JWT_SECRET"],
        secret_key=secrets["SECRET_KEY"],
        internal_token=secrets["INTERNAL_TOKEN"],
        jwt_secret=secrets["JWT_SECRET"],
    )
    layout.config.write_text(text)
    layout.config.chmod(0o600)


def prepare_config(layout: Layout, flavor: str, lan_ip: str) -> None:
    """Write config.ini unless setup was already finished.

    A config without INSTALL_LOCK = true is replaced only when the database has no
    users. The old config and database are moved to backup/, never deleted.
    """
    if layout.config.exists() and has_line(layout.config.read_text(), "INSTALL_LOCK = true"):
        log(f"Keeping existing config: {layout.config}")
        return

    users = count_users(layout.db)
    if users > 0:
        die(f"The database already has {users} user(s). Not replacing {layout.config}; finish the setup manually.")

    if user_unit_active(USER_UNIT):
        log(f"Stopping {USER_UNIT} before replacing the database")
        systemctl_user("stop", USER_UNIT)

    archive = layout.backup / f"pre-config-{stamp()}"
    for path in [layout.config, layout.db, layout.db.with_name(layout.db.name + "-wal"), layout.db.with_name(layout.db.name + "-shm")]:
        if path.exists():
            archive.mkdir(parents=True, exist_ok=True)
            log(f"Moving {path} -> {archive}/")
            shutil.move(str(path), str(archive / path.name))

    write_config(layout, flavor, lan_ip)


def update_root_url(layout: Layout, lan_ip: str) -> None:
    """Keep ROOT_URL in step with the LAN address and restart the service if it changed."""
    if not layout.config.exists():
        return
    updated, changed = update_root_url_text(layout.config.read_text(), lan_ip)
    if not changed:
        log(f"ROOT_URL is already {root_url(lan_ip)}")
        return
    backup_file(layout.config)
    layout.config.write_text(updated)
    log(f"Set ROOT_URL to {root_url(lan_ip)}")
    systemctl_user("try-restart", USER_UNIT, check=False)
