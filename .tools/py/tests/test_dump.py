"""The standalone dump script: archive check and retention in the backup folder."""

import pathlib
import tempfile
import unittest
import zipfile
import importlib.util

import _path  # noqa: F401

spec = importlib.util.spec_from_file_location("dump", pathlib.Path(_path.PY_DIR) / "dump.py")
dump = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dump)


class DumpTests(unittest.TestCase):
    def test_good_archive_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ok.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("gitea-db.sql", "SELECT 1;")
            dump.verify_archive(path)

    def test_corrupt_archive_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("data.txt", "x" * 1000)
            raw = bytearray(path.read_bytes())
            raw[60] ^= 0xFF  # damage the stored data
            path.write_bytes(bytes(raw))
            with self.assertRaises((RuntimeError, zipfile.BadZipFile)):
                dump.verify_archive(path)

    def test_prune_keeps_newest_seven(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup = pathlib.Path(tmp)
            for index in range(9):
                path = backup / f"git-local-{index:02d}.zip"
                path.write_bytes(b"x")
                ts = 1_700_000_000 + index * 60
                import os
                os.utime(path, (ts, ts))
            original = dump.BACKUP
            dump.BACKUP = backup
            try:
                dump.prune_old_dumps()
            finally:
                dump.BACKUP = original
            remaining = sorted(p.name for p in backup.glob("git-local-*.zip"))
            self.assertEqual(len(remaining), 7)
            self.assertNotIn("git-local-00.zip", remaining)
            self.assertNotIn("git-local-01.zip", remaining)
            self.assertIn("git-local-08.zip", remaining)


if __name__ == "__main__":
    unittest.main()
