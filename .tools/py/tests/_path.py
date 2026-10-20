"""Make the .tools/py package and dump.py importable from the tests."""

import pathlib
import sys

PY_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))
