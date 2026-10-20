"""config.ini template and the ROOT_URL rewrite."""

import unittest

import _path  # noqa: F401
from git_local import config


class ConfigTests(unittest.TestCase):
    def test_root_url_is_replaced(self):
        source = "[server]\nROOT_URL = http://git.local/\nHTTP_PORT = 3000\n"
        updated, changed = config.update_root_url_text(source, "192.168.0.2")
        self.assertTrue(changed)
        self.assertIn("ROOT_URL = https://192.168.0.2:8080/", updated.splitlines())

    def test_root_url_unchanged(self):
        _, changed = config.update_root_url_text("ROOT_URL = https://192.168.0.2:8080/\n", "192.168.0.2")
        self.assertFalse(changed)

    def test_template_keeps_required_settings(self):
        text = config.config_text(
            base_dir="/mnt/dados/git.local",
            lan_ip="192.168.0.2",
            lfs_jwt_secret="L",
            secret_key="S",
            internal_token="I",
            jwt_secret="J",
        )
        lines = set(text.splitlines())
        for expected in [
            "ROOT_URL = https://192.168.0.2:8080/",
            "SSH_USER = git",
            "BUILTIN_SSH_SERVER_USER = git",
            "SSH_LISTEN_PORT = 2222",
            "SSH_PORT = 22",
            "SSH_DOMAIN = local",
            "SSH_CREATE_AUTHORIZED_KEYS_FILE = false",
            "USE_COMPAT_SSH_URI = false",
            "INSTALL_LOCK = true",
            "PASSWORD_HASH_ALGO = argon2",
            "DISABLE_REGISTRATION = true",
            "REQUIRE_SIGNIN_VIEW = true",
            "ENABLE_OPENID_SIGNUP = false",
            "PATH = /mnt/dados/git.local/data/git-local.db",
            "WORK_PATH = /mnt/dados/git.local",
        ]:
            self.assertIn(expected, lines)
        self.assertNotIn("/seagate", text)

    def test_template_sets_blue_default_theme(self):
        text = config.config_text("/mnt/d/git.local", "192.168.0.2", "L", "S", "I", "J")
        self.assertIn("[ui]", text.splitlines())
        self.assertIn("DEFAULT_THEME = azul-auto", text.splitlines())

    def test_has_line_is_exact(self):
        self.assertTrue(config.has_line("A\nINSTALL_LOCK = true\n", "INSTALL_LOCK = true"))
        self.assertFalse(config.has_line("INSTALL_LOCK = true2\n", "INSTALL_LOCK = true"))


if __name__ == "__main__":
    unittest.main()
