"""Command dispatch and the top-level error handling."""

from __future__ import annotations

import subprocess
import sys

from .install import cmd_install
from .paths import Layout
from .state import load_root
from .uninstall import cmd_check_ssh, cmd_status, cmd_uninstall
from .util import Fatal, die

USAGE = """Usage: python3 -m git_local {install|uninstall|status|check-ssh|dump|help}

  install    Choose the data mount point, check packages, then install and configure
             Gitea or Forgejo. Set GIT_LOCAL_ROOT to skip the mount point question.
  uninstall  Remove services, timer, nginx files and dump script (keeps data)
  status     Show the service, dump timer, nginx and ~/.ssh/config status
  check-ssh  Check that ~/.ssh/config has the 'local' host with port 2222 and user git
  dump       Create a dump now (stops the server while it runs)
  help       Show this message
"""


def cmd_dump() -> None:
    layout: Layout = load_root()
    if not layout.dump_script.exists():
        die(f"{layout.dump_script} not found. Run make install first.")
    subprocess.run([sys.executable, str(layout.dump_script)], check=True)


COMMANDS = {
    "install": cmd_install,
    "uninstall": cmd_uninstall,
    "status": cmd_status,
    "check-ssh": cmd_check_ssh,
    "dump": cmd_dump,
}


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "help"
    if command in {"help", "-h", "--help"}:
        print(USAGE, end="")
        return 0
    if command not in COMMANDS:
        print(USAGE, end="", file=sys.stderr)
        print(f"ERROR: Unknown command: {command}", file=sys.stderr)
        return 1
    try:
        COMMANDS[command]()
    except Fatal as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except subprocess.CalledProcessError as error:
        print(f"ERROR: command failed: {' '.join(map(str, error.cmd))}", file=sys.stderr)
        return error.returncode or 1
    return 0
