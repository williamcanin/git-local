#!/usr/bin/env bash
# Create a full Gitea/Forgejo dump (database, repositories, LFS, attachments
# and config) in /seagate/git.local/backup, then keep only the newest dumps.
#
# The server is stopped while the dump runs so the SQLite database is not
# written to during the copy. It is started again on exit if it was running.
#
# Usage: .tools/dump.sh

set -euo pipefail

readonly SEAGATE_DIR="/seagate"
readonly BASE_DIR="$SEAGATE_DIR/git.local"
readonly CONFIG_FILE="$BASE_DIR/config/config.ini"
readonly FLAVOR_FILE="$BASE_DIR/config/flavor"
readonly BACKUP_DIR="$BASE_DIR/backup"
readonly TEMP_DIR="$BACKUP_DIR/tmp"
readonly SERVICE="git-local.service"
readonly KEEP_DUMPS=7

log() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ -f "$FLAVOR_FILE" ]] || die "$FLAVOR_FILE not found. Run 'make install' first."
[[ -f "$CONFIG_FILE" ]] || die "$CONFIG_FILE not found. Run 'make install' first."
mountpoint -q "$SEAGATE_DIR" || die "$SEAGATE_DIR is not mounted; refusing to dump."

FLAVOR="$(< "$FLAVOR_FILE")"
DUMP_FILE="$BACKUP_DIR/git-local-$(date +%m-%d-%Y_%H-%M-%S).zip"

WAS_ACTIVE=false
if systemctl --user is-active --quiet "$SERVICE"; then
  WAS_ACTIVE=true
fi

cleanup() {
  local status=$?
  if (( status != 0 )); then
    log "Dump failed; removing partial file $DUMP_FILE"
    rm -f -- "$DUMP_FILE"
  fi
  rm -rf -- "$TEMP_DIR"
  if [[ "$WAS_ACTIVE" == true ]]; then
    log "Starting $SERVICE"
    systemctl --user start "$SERVICE" || printf 'WARNING: could not start %s\n' "$SERVICE" >&2
  fi
  exit "$status"
}
trap cleanup EXIT

# Keep the newest $KEEP_DUMPS archives and delete the rest.
prune_old_dumps() {
  local file
  while IFS= read -r file; do
    log "Removing old dump $file"
    rm -f -- "$file"
  done < <(find "$BACKUP_DIR" -maxdepth 1 -name 'git-local-*.zip' -printf '%T@ %p\n' | sort -rn | tail -n +"$((KEEP_DUMPS + 1))" | cut -d' ' -f2-)
}

mkdir -p "$TEMP_DIR"

if [[ "$WAS_ACTIVE" == true ]]; then
  log "Stopping $SERVICE"
  systemctl --user stop "$SERVICE"
fi

log "Dumping $FLAVOR to $DUMP_FILE"
"$FLAVOR" dump --config "$CONFIG_FILE" --file "$DUMP_FILE" --tempdir "$TEMP_DIR"

log "Verifying archive"
unzip -tq "$DUMP_FILE" >/dev/null

prune_old_dumps
log "Dump complete: $DUMP_FILE"
