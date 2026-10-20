#!/usr/bin/env python3
"""Create a full Gitea/Forgejo dump in <root>/git.local/backup, keep the newest dumps.

The server is stopped while the dump runs so the SQLite database is not written to
during the copy. It is started again on exit if it was running.

Installed by make install to <root>/git.local/bin/dump.py. The paths follow from the
script's own location, so this file does not depend on the project folder.
Standard library only.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import shutil
import subprocess
import sys
import zipfile

KEEP_DUMPS = 7
SERVICE = "git-local.service"

BASE = pathlib.Path(__file__).resolve().parent.parent
ROOT = BASE.parent
CONFIG = BASE / "config" / "config.ini"
FLAVOR_FILE = BASE / "config" / "flavor"
BACKUP = BASE / "backup"
TEMP = BACKUP / "tmp"


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def service_active() -> bool:
    result = subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE], check=False)
    return result.returncode == 0


def verify_archive(path: pathlib.Path) -> None:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
    if bad is not None:
        raise RuntimeError(f"corrupt entry in {path}: {bad}")


def prune_old_dumps() -> None:
    entries = [(path.stat().st_mtime, path) for path in BACKUP.glob("git-local-*.zip")]
    entries.sort(key=lambda item: item[0], reverse=True)
    for _, path in entries[KEEP_DUMPS:]:
        log(f"Removing old dump {path}")
        path.unlink()


def main() -> int:
    if not FLAVOR_FILE.exists():
        die(f"{FLAVOR_FILE} not found. Run make install first.")
    if not CONFIG.exists():
        die(f"{CONFIG} not found. Run make install first.")
    if not os.path.ismount(ROOT):
        die(f"{ROOT} is not mounted; refusing to dump.")

    flavor = FLAVOR_FILE.read_text().strip()
    stamp = dt.datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
    dump_file = BACKUP / f"git-local-{stamp}.zip"
    was_active = service_active()

    BACKUP.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(parents=True, exist_ok=True)
    status = 1
    try:
        if was_active:
            log(f"Stopping {SERVICE}")
            subprocess.run(["systemctl", "--user", "stop", SERVICE], check=True)

        log(f"Dumping {flavor} to {dump_file}")
        subprocess.run(
            [flavor, "dump", "--config", str(CONFIG), "--file", str(dump_file), "--tempdir", str(TEMP)],
            check=True,
        )

        log("Verifying archive")
        verify_archive(dump_file)

        prune_old_dumps()
        log(f"Dump complete: {dump_file}")
        status = 0
    except (subprocess.CalledProcessError, RuntimeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if dump_file.exists():
            log(f"Dump failed; removing partial file {dump_file}")
            dump_file.unlink()
    finally:
        shutil.rmtree(TEMP, ignore_errors=True)
        if was_active:
            log(f"Starting {SERVICE}")
            started = subprocess.run(["systemctl", "--user", "start", SERVICE], check=False)
            if started.returncode != 0:
                print(f"WARNING: could not start {SERVICE}", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main())
