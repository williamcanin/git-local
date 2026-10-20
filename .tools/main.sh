#!/usr/bin/env bash
# Install and configure a self-hosted Git server (Gitea or Forgejo) on Arch Linux.
#
# Usage: .tools/main.sh {install|uninstall|status|dump|help}

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PROJECT_DIR
readonly SRC_DIR="$PROJECT_DIR/src"

readonly SEAGATE_DIR="/seagate"
readonly BASE_DIR="$SEAGATE_DIR/git.local"
readonly CONFIG_FILE="$BASE_DIR/config/config.ini"
readonly FLAVOR_FILE="$BASE_DIR/config/flavor"
readonly DB_FILE="$BASE_DIR/data/git-local.db"
readonly HTTP_PORT=3000
readonly SSH_PORT=2222

readonly USER_UNIT_DIR="$HOME/.config/systemd/user"
readonly USER_UNIT="git-local.service"
readonly DUMP_SERVICE="git-local-dump.service"
readonly DUMP_TIMER="git-local-dump.timer"
readonly LEGACY_UNIT="gitea.service"

readonly SSH_CONFIG="$HOME/.ssh/config"
readonly SSH_CLIENT_HOST="local"
readonly AUTHORIZED_KEYS="$HOME/.ssh/authorized_keys"

readonly FSTAB_LINE="UUID=93E4-3F3A /seagate exfat uid=boss,gid=boss,dmask=007,fmask=007,nofail,x-gvfs-show 0 0"

FLAVOR=""
FSTAB_OK=true

log() { printf '==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Run a command as root, using sudo when not already root.
as_root() {
  if [[ $EUID -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

# Back up an existing file as <file>.bak-MM-DD-YYYY_HH-MM-SS.
# Extra arguments are a command prefix, e.g. "as_root" for system files.
backup_file() {
  local path="$1"
  shift
  if [[ -e "$path" || -L "$path" ]]; then
    local stamp backup
    stamp="$(date +%m-%d-%Y_%H-%M-%S)"
    backup="$path.bak-$stamp"
    log "Backing up $path -> $backup"
    "$@" cp -a -- "$path" "$backup"
  fi
}

require_arch() {
  [[ -f /etc/arch-release ]] || die "This installer only supports Arch Linux."
}

choose_flavor() {
  local choice
  printf '\nSelect the Git server to install:\n'
  printf '  [1] Forgejo [Default]\n'
  printf '  [2] Gitea\n'
  read -r -p 'Option [1]: ' choice
  case "${choice:-1}" in
    1) FLAVOR="forgejo" ;;
    2) FLAVOR="gitea" ;;
    *) die "Invalid option: $choice" ;;
  esac
  log "Selected: $FLAVOR"
}

# The data lives on the external drive, so refuse to continue if it is not
# mounted: creating directories there would write to the root filesystem.
check_seagate() {
  if ! mountpoint -q "$SEAGATE_DIR"; then
    die "$SEAGATE_DIR is not mounted. Mount it first."
  fi
  log "$SEAGATE_DIR is mounted"

  if ! grep -qE "^[^#]*[[:space:]]${SEAGATE_DIR}[[:space:]]" /etc/fstab; then
    FSTAB_OK=false
    warn "/etc/fstab has no entry for $SEAGATE_DIR. Add this line, run 'sudo systemctl daemon-reload' and then 'make install' again:"
    printf '\n    %s\n\n' "$FSTAB_LINE" >&2
  fi
}

install_packages() {
  local -a packages
  case "$FLAVOR" in
    forgejo) packages=(forgejo forgejo-cli) ;;
    gitea) packages=(gitea gitea-runner) ;;
  esac
  log "Installing packages: unzip ${packages[*]}"
  as_root pacman -S --needed unzip "${packages[@]}"
}

create_directories() {
  log "Creating directories under $BASE_DIR"
  mkdir -p "$BASE_DIR/config" "$BASE_DIR/data/lfs" "$BASE_DIR/data/repositories" "$BASE_DIR/log" "$BASE_DIR/backup"
}

# Number of user accounts in the database; 0 when the database does not exist
# or its schema has not been created yet.
count_users() {
  if [[ ! -f "$DB_FILE" ]]; then
    echo 0
    return
  fi
  python3 - "$DB_FILE" <<'PY'
import sqlite3
import sys

con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
try:
    print(con.execute("SELECT COUNT(*) FROM user").fetchone()[0])
except sqlite3.OperationalError:
    print(0)
PY
}

write_config() {
  log "Generating config: $CONFIG_FILE"
  local secret_key internal_token jwt_secret lfs_jwt_secret
  secret_key="$("$FLAVOR" generate secret SECRET_KEY)"
  internal_token="$("$FLAVOR" generate secret INTERNAL_TOKEN)"
  jwt_secret="$("$FLAVOR" generate secret JWT_SECRET)"
  lfs_jwt_secret="$("$FLAVOR" generate secret LFS_JWT_SECRET)"

  cat > "$CONFIG_FILE" <<EOF
APP_NAME = Git Local
RUN_MODE = prod
RUN_USER = boss
WORK_PATH = $BASE_DIR

[actions]
ENABLED = false

[server]
DOMAIN = git.local
HTTP_ADDR = 127.0.0.1
HTTP_PORT = $HTTP_PORT
ROOT_URL = http://git.local/
APP_DATA_PATH = $BASE_DIR/data
LFS_START_SERVER = true
LFS_JWT_SECRET = $lfs_jwt_secret
DISABLE_SSH = false
START_SSH_SERVER = true
SSH_USER = boss
BUILTIN_SSH_SERVER_USER = boss
SSH_DOMAIN = git.local
SSH_LISTEN_PORT = $SSH_PORT
SSH_PORT = $SSH_PORT
SSH_CREATE_AUTHORIZED_KEYS_FILE = false
SSH_AUTHORIZED_KEYS_BACKUP = false
USE_COMPAT_SSH_URI = true

[database]
DB_TYPE = sqlite3
PATH = $BASE_DIR/data/git-local.db

[repository]
ROOT = $BASE_DIR/data/repositories

[repository.pull-request]
DEFAULT_MERGE_STYLE = merge

[repository.signing]
DEFAULT_TRUST_MODEL = committer

[log]
MODE = console
LEVEL = info
ROOT_PATH = $BASE_DIR/log

[security]
INSTALL_LOCK = true
SECRET_KEY = $secret_key
INTERNAL_TOKEN = $internal_token
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
JWT_SECRET = $jwt_secret
EOF
  chmod 600 "$CONFIG_FILE"
}

# Write config.ini unless setup was already finished. A config without
# INSTALL_LOCK = true is replaced only when the database has no users; the old
# config and database files are moved to backup/, never deleted.
prepare_config() {
  if [[ -f "$CONFIG_FILE" ]] && grep -qx 'INSTALL_LOCK = true' "$CONFIG_FILE"; then
    log "Keeping existing config: $CONFIG_FILE"
    return
  fi

  local users
  users="$(count_users)"
  if (( users > 0 )); then
    die "The database already has $users user(s). Not replacing $CONFIG_FILE; finish the setup manually."
  fi

  if systemctl --user is-active --quiet "$USER_UNIT"; then
    log "Stopping $USER_UNIT before replacing the database"
    systemctl --user stop "$USER_UNIT"
  fi

  local archive path
  archive="$BASE_DIR/backup/pre-config-$(date +%m-%d-%Y_%H-%M-%S)"
  for path in "$CONFIG_FILE" "$DB_FILE" "$DB_FILE-wal" "$DB_FILE-shm"; do
    if [[ -e "$path" ]]; then
      mkdir -p "$archive"
      log "Moving $path -> $archive/"
      mv -- "$path" "$archive/"
    fi
  done

  write_config
}

# dump.sh reads this file to know which binary to call.
write_flavor_file() {
  printf '%s\n' "$FLAVOR" > "$FLAVOR_FILE"
  log "Recorded flavor in $FLAVOR_FILE"
}

# Copy src/etc/** to /etc/**, backing up any file it replaces.
install_etc_files() {
  local src dest
  while IFS= read -r -d '' src; do
    dest="/etc/${src#"$SRC_DIR/etc/"}"
    backup_file "$dest" as_root
    as_root install -D -m 644 "$src" "$dest"
    log "Installed $dest"
  done < <(find "$SRC_DIR/etc" -type f -print0)
}

install_user_file() {
  local src="$1" dest="$2"
  backup_file "$dest"
  install -m 644 "$src" "$dest"
  log "Installed $dest"
}

install_user_units() {
  mkdir -p "$USER_UNIT_DIR"
  install_user_file "$SRC_DIR/.config/systemd/user/$FLAVOR/git-local.service" "$USER_UNIT_DIR/$USER_UNIT"
  install_user_file "$SRC_DIR/.config/systemd/user/$DUMP_SERVICE" "$USER_UNIT_DIR/$DUMP_SERVICE"
  install_user_file "$SRC_DIR/.config/systemd/user/$DUMP_TIMER" "$USER_UNIT_DIR/$DUMP_TIMER"
  systemctl --user daemon-reload
}

# Gitea and Forgejo both use port $HTTP_PORT, so the old user unit must not run.
# Its data in /seagate/gitea is not touched.
disable_legacy_unit() {
  if systemctl --user cat "$LEGACY_UNIT" >/dev/null 2>&1; then
    log "Disabling $LEGACY_UNIT (its data in /seagate/gitea is kept)"
    systemctl --user disable --now "$LEGACY_UNIT"
  fi
}

# Linger lets user services start at boot without a login session.
enable_linger() {
  local user
  user="$(id -un)"
  if [[ "$(loginctl show-user "$user" --property=Linger --value)" == "yes" ]]; then
    log "Linger already enabled for $user"
  else
    log "Enabling linger for $user"
    as_root loginctl enable-linger "$user"
  fi
}

reload_nginx() {
  log "Testing nginx configuration"
  if ! as_root nginx -t; then
    warn "nginx configuration test failed; nginx was not reloaded."
    return 1
  fi

  if systemctl is-active --quiet nginx; then
    as_root systemctl reload nginx
  else
    as_root systemctl enable --now nginx
  fi
}

# The old Gitea wrote its key to authorized_keys, pointing at its own database.
# Remove that entry (after a backup) so the stale key cannot match new key IDs.
remove_legacy_gitea_key() {
  [[ -f "$AUTHORIZED_KEYS" ]] || return 0
  if ! grep -qE '^(# gitea public key|command="/usr/bin/gitea )' "$AUTHORIZED_KEYS"; then
    return 0
  fi
  backup_file "$AUTHORIZED_KEYS"
  sed -i -E -e '/^# gitea public key/d' -e '/^command="\/usr\/bin\/gitea /d' "$AUTHORIZED_KEYS"
  log "Removed the legacy Gitea key from $AUTHORIZED_KEYS"
}

# The "local" host alias must use the built-in SSH port of Forgejo.
configure_ssh_client() {
  if [[ ! -f "$SSH_CONFIG" ]]; then
    warn "$SSH_CONFIG not found; add 'Port $SSH_PORT' to your '$SSH_CLIENT_HOST' host manually."
    return
  fi

  # Some ssh config files use CRLF line endings; keep the new line consistent with them.
  local eol=""
  if grep -q $'\r' "$SSH_CONFIG"; then
    eol=$'\r'
  fi

  if awk -v host="$SSH_CLIENT_HOST" -v port="$SSH_PORT" '
      { sub(/\r$/, "") }
      /^[Hh]ost[[:space:]]/ { inblock = ($2 == host) }
      inblock && $1 ~ /^[Pp]ort$/ && $2 == port { found = 1 }
      END { exit !found }' "$SSH_CONFIG"; then
    log "Host '$SSH_CLIENT_HOST' already uses port $SSH_PORT"
    return
  fi

  if ! grep -qE "^Host[[:space:]]+${SSH_CLIENT_HOST}[[:space:]]*\$" "$SSH_CONFIG"; then
    warn "No 'Host $SSH_CLIENT_HOST' block in $SSH_CONFIG; add 'Port $SSH_PORT' to it manually."
    return
  fi

  backup_file "$SSH_CONFIG"
  sed -i -E "/^Host[[:space:]]+${SSH_CLIENT_HOST}[[:space:]]*\$/a\\    Port ${SSH_PORT}${eol}" "$SSH_CONFIG"
  log "Set Port $SSH_PORT for host '$SSH_CLIENT_HOST' in $SSH_CONFIG"
}

# Run database migrations and create the first administrator from the terminal,
# replacing the web setup page.
create_admin() {
  "$FLAVOR" migrate --config "$CONFIG_FILE"

  if (( $(count_users) > 0 )); then
    log "An administrator already exists; skipping account creation"
    return
  fi

  local username email
  read -r -p 'Administrator username: ' username
  read -r -p 'Administrator email: ' email
  [[ -n "$username" && -n "$email" ]] || die "Username and email are required."

  log "Creating administrator '$username'. The random password is printed once; it must be changed at first login."
  "$FLAVOR" admin user create --admin --username "$username" --email "$email" \
    --random-password --must-change-password --config "$CONFIG_FILE"
}

start_services() {
  log "Enabling the daily dump timer"
  systemctl --user enable --now "$DUMP_TIMER"

  if [[ "$FSTAB_OK" != true ]]; then
    warn "$USER_UNIT was not started because $SEAGATE_DIR is not in /etc/fstab."
    return
  fi
  log "Enabling and starting $USER_UNIT"
  systemctl --user enable --now "$USER_UNIT"
}

cmd_install() {
  require_arch
  choose_flavor
  check_seagate
  install_packages
  create_directories
  prepare_config
  write_flavor_file
  install_etc_files
  install_user_units
  disable_legacy_unit
  enable_linger
  reload_nginx || true
  remove_legacy_gitea_key
  configure_ssh_client
  create_admin
  start_services
  log "Done. Open http://git.local and sign in with the administrator account."
}

cmd_dump() {
  "$PROJECT_DIR/.tools/dump.sh"
}

cmd_uninstall() {
  log "Stopping and disabling the service and the dump timer"
  systemctl --user disable --now "$DUMP_TIMER" "$USER_UNIT" || true
  rm -f "$USER_UNIT_DIR/$USER_UNIT" "$USER_UNIT_DIR/$DUMP_SERVICE" "$USER_UNIT_DIR/$DUMP_TIMER"
  systemctl --user daemon-reload
  log "Service removed. Packages, /etc files and $BASE_DIR were kept."
}

cmd_status() {
  systemctl --user status "$USER_UNIT" --no-pager || true
  systemctl --user list-timers "$DUMP_TIMER" --no-pager || true
  as_root nginx -t || true
}

usage() {
  cat <<EOF
Usage: $(basename "$0") {install|uninstall|status|dump|help}

  install    Install and configure Gitea or Forgejo
  uninstall  Stop the Git Local service and timer, remove their user units
  status     Show the service, dump timer and nginx status
  dump       Create a dump now (stops the server while it runs)
  help       Show this message
EOF
}

main() {
  case "${1:-help}" in
    install) cmd_install ;;
    uninstall) cmd_uninstall ;;
    status) cmd_status ;;
    dump) cmd_dump ;;
    help | -h | --help) usage ;;
    *) usage >&2; die "Unknown command: $1" ;;
  esac
}

main "$@"
