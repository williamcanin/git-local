"""Entry point: python3 -m git_local <command>."""

import sys

from .cli import main

sys.exit(main(sys.argv))
