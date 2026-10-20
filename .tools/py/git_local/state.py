"""Installation state carried through one run, and loading the recorded data root."""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass
from typing import Optional

from .paths import Layout, ROOT_RECORD
from .util import die


@dataclass
class State:
    layout: Optional[Layout] = None
    flavor: str = ""
    lan_ip: str = ""
    fstab_ok: bool = True


def load_root() -> Layout:
    """The data root from GIT_LOCAL_ROOT, or the record left by the last install."""
    recorded = os.environ.get("GIT_LOCAL_ROOT", "").strip()
    if not recorded and ROOT_RECORD.exists():
        recorded = ROOT_RECORD.read_text().strip()
    if not recorded:
        die(f"No data root recorded in {ROOT_RECORD}. Run make install first, or set GIT_LOCAL_ROOT to the mount point.")
    return Layout(pathlib.Path(recorded))
