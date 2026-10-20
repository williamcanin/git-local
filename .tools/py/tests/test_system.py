"""System helpers that work on temporary directories: certificates, nginx rendering, client script."""

import pathlib
import tempfile
import unittest
from unittest import mock

import _path  # noqa: F401
from git_local import paths, system, text


class CertificateTests(unittest.TestCase):
    def _source(self, tmp, with_key=True):
        source = pathlib.Path(tmp) / "cert"
        source.mkdir()
        (source / "git.local.pem").write_text("CERT")
        if with_key:
            (source / "git.local-key.pem").write_text("KEY")
        return source

    def test_copies_both_files_with_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._source(tmp)
            layout = paths.Layout(pathlib.Path(tmp) / "root")
            with mock.patch.object(system, "SRC_DIR", pathlib.Path(tmp)):
                self.assertTrue(system.install_cert_files(layout))
            key = layout.base / "cert" / "git.local-key.pem"
            cert = layout.base / "cert" / "git.local.pem"
            self.assertEqual(key.read_text(), "KEY")
            self.assertEqual(cert.read_text(), "CERT")
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)
            self.assertEqual(cert.stat().st_mode & 0o777, 0o644)
            self.assertTrue(source.exists())

    def test_missing_key_is_reported_not_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._source(tmp, with_key=False)
            layout = paths.Layout(pathlib.Path(tmp) / "root")
            with mock.patch.object(system, "SRC_DIR", pathlib.Path(tmp)):
                self.assertFalse(system.install_cert_files(layout))
            self.assertFalse((layout.base / "cert" / "git.local-key.pem").exists())


class NginxRenderTests(unittest.TestCase):
    def test_certificate_paths_use_the_data_root(self):
        source = "ssl_certificate @ROOT@/git.local/cert/git.local.pem;\nssl_certificate_key @ROOT@/git.local/cert/git.local-key.pem;\n"
        rendered = text.render_unit(source, "/mnt/dados", "192.168.0.2")
        self.assertIn("ssl_certificate /mnt/dados/git.local/cert/git.local.pem;", rendered)
        self.assertNotIn("@ROOT@", rendered)

    def test_project_nginx_files_render_without_placeholders(self):
        etc = paths.SRC_DIR / "etc" / "nginx" / "conf.d"
        for path in etc.glob("git-local*.conf"):
            rendered = text.render_unit(path.read_text(), "/mnt/dados", "192.168.0.2")
            self.assertNotIn("@ROOT@", rendered, path)
            self.assertIn("/mnt/dados/git.local/cert/git.local.pem", rendered, path)


class ClientScriptTests(unittest.TestCase):
    def test_script_uses_gitlocal_token_name(self):
        script = paths.CLIENT_SCRIPT_SOURCE.read_text()
        self.assertIn("GITLOCAL_TOKEN", script)
        self.assertNotIn("FORGEJO_TOKEN", script)


if __name__ == "__main__":
    unittest.main()
