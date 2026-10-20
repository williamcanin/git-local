"""Pure text helpers: fstab, hosts, backups, units, legacy keys, pruning."""

import unittest

import _path  # noqa: F401
from git_local import text


class TextTests(unittest.TestCase):
    def test_fstab_entry_for_root(self):
        fstab = "# comment\nUUID=1 / ext4 rw 0 1\nUUID=93E4 /seagate exfat nofail 0 0\n"
        self.assertTrue(text.fstab_has_mount(fstab, "/seagate"))
        self.assertFalse(text.fstab_has_mount(fstab, "/mnt/dados"))
        self.assertFalse(text.fstab_has_mount("#UUID=1 /seagate exfat\n", "/seagate"))

    def test_hosts_name_in_alias_list(self):
        hosts = "127.0.0.1 localhost\n192.168.0.2 gitea.local git.local\n"
        self.assertEqual(text.hosts_address(hosts, "git.local"), "192.168.0.2")

    def test_hosts_commented_line_is_ignored(self):
        self.assertIsNone(text.hosts_address("#192.168.0.2 git.local\n", "git.local"))
        self.assertIsNone(text.hosts_address("127.0.0.1 localhost\n", "git.local"))

    def test_newest_backup_is_chosen_by_name_time(self):
        names = [
            "/etc/nginx/nginx.conf.bak-10-20-2026_09-00-00",
            "/etc/nginx/nginx.conf.bak-10-20-2026_14-30-00",
            "/etc/nginx/nginx.conf.bak-09-30-2026_23-59-59",
        ]
        self.assertEqual(text.latest_backup(names), "/etc/nginx/nginx.conf.bak-10-20-2026_14-30-00")

    def test_no_backup(self):
        self.assertIsNone(text.latest_backup([]))
        self.assertIsNone(text.latest_backup(["/etc/x.conf.bak-notadate"]))

    def test_backup_name_format(self):
        self.assertEqual(text.backup_name("/etc/x.conf", "10-20-2026_12-00-00"), "/etc/x.conf.bak-10-20-2026_12-00-00")

    def test_placeholders_are_replaced(self):
        source = "ExecStart=/usr/bin/forgejo web --config @ROOT@/git.local/config/config.ini\nANNOUNCE @IP@\n"
        rendered = text.render_unit(source, "/mnt/dados", "192.168.0.2")
        self.assertIn("--config /mnt/dados/git.local/config/config.ini", rendered)
        self.assertIn("ANNOUNCE 192.168.0.2", rendered)
        self.assertNotIn("@", rendered)

    def test_legacy_gitea_key_lines_are_removed(self):
        source = '# gitea public key\ncommand="/usr/bin/gitea --config=/x serv key-1",restrict ssh-ed25519 AAA user-1\nssh-ed25519 AAAOTHER keep\n'
        updated, changed = text.remove_legacy_gitea_lines(source)
        self.assertTrue(changed)
        self.assertEqual(updated, "ssh-ed25519 AAAOTHER keep\n")

    def test_prune_keeps_newest(self):
        entries = [(1.0, "a"), (5.0, "e"), (3.0, "c"), (4.0, "d"), (2.0, "b")]
        self.assertEqual(text.files_to_prune(entries, keep=3), ["b", "a"])
        self.assertEqual(text.files_to_prune(entries, keep=7), [])


if __name__ == "__main__":
    unittest.main()
