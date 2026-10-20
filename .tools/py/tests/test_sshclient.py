"""The 'Host local' block in ~/.ssh/config, CRLF-aware."""

import unittest

import _path  # noqa: F401
from git_local import sshclient


class SshConfigTests(unittest.TestCase):
    CRLF_BLOCK = (
        "# Git Local\r\n"
        "Host local\r\n"
        "    HostName git.local\r\n"
        "    User boss\r\n"
        "    IdentityFile ~/.ssh/local_williamcanin\r\n"
        "    IdentitiesOnly yes\r\n"
        "\r\n"
        "Host github\r\n"
        "    User git\r\n"
    )

    def test_block_is_found_and_other_blocks_are_ignored(self):
        self.assertTrue(sshclient.ssh_block_exists(self.CRLF_BLOCK, "local"))
        self.assertFalse(sshclient.ssh_block_exists(self.CRLF_BLOCK, "gitlab"))

    def test_fix_adds_port_and_replaces_user_keeping_crlf(self):
        fixed, changes = sshclient.fix_ssh_block(self.CRLF_BLOCK, "local", 2222, "git")
        self.assertEqual(changes, ["Port 2222", "User git"])
        self.assertIn("    Port 2222\r\n", fixed)
        self.assertIn("    User git\r\n", fixed)
        self.assertNotIn("User boss", fixed)
        self.assertEqual(fixed.count("\n"), fixed.count("\r\n"))
        self.assertTrue(fixed.endswith("Host github\r\n    User git\r\n"))

    def test_fix_is_idempotent(self):
        once, _ = sshclient.fix_ssh_block(self.CRLF_BLOCK, "local", 2222, "git")
        twice, changes = sshclient.fix_ssh_block(once, "local", 2222, "git")
        self.assertEqual(changes, [])
        self.assertEqual(once, twice)

    def test_fix_adds_user_when_missing(self):
        source = "Host local\n    HostName git.local\n"
        fixed, changes = sshclient.fix_ssh_block(source, "local", 2222, "git")
        self.assertEqual(changes, ["Port 2222", "User git"])
        self.assertIn("    User git", fixed.splitlines())

    def test_missing_block_is_not_created(self):
        source = "Host github\n    User git\n"
        fixed, changes = sshclient.fix_ssh_block(source, "local", 2222, "git")
        self.assertEqual(changes, [])
        self.assertEqual(fixed, source)

    def test_checks_port_and_user(self):
        fixed, _ = sshclient.fix_ssh_block(self.CRLF_BLOCK, "local", 2222, "git")
        self.assertTrue(sshclient.ssh_block_has(fixed, "local", "port", "2222"))
        self.assertTrue(sshclient.ssh_block_has(fixed, "local", "user", "git"))
        self.assertFalse(sshclient.ssh_block_has(self.CRLF_BLOCK, "local", "port", "2222"))


if __name__ == "__main__":
    unittest.main()
