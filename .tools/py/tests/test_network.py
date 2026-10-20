"""LAN address: fixed or DHCP, from simulated ip and nmcli output."""

import unittest

import _path  # noqa: F401
from git_local import network


class AddressTests(unittest.TestCase):
    ADDR_STATIC = "3: br0    inet 192.168.0.2/24 brd 192.168.0.255 scope global noprefixroute br0       valid_lft forever preferred_lft forever"
    ADDR_DYNAMIC = "3: br0    inet 192.168.0.2/24 brd 192.168.0.255 scope global dynamic noprefixroute br0   valid_lft 86000sec preferred_lft 86000sec"

    @staticmethod
    def nm(answers):
        return lambda cmd: answers.get(tuple(cmd), "")

    def test_static_address_from_nm_manual(self):
        method = network.address_method("br0", "192.168.0.2", self.ADDR_STATIC,
                                        self.nm({("nmcli", "-g", "GENERAL.CONNECTION", "device", "show", "br0"): "br0",
                                                 ("nmcli", "-g", "ipv4.method", "connection", "show", "br0"): "manual"}))
        self.assertEqual(method, "static")

    def test_dhcp_from_kernel_dynamic_flag(self):
        self.assertEqual(network.address_method("br0", "192.168.0.2", self.ADDR_DYNAMIC, self.nm({})), "dhcp")

    def test_dhcp_from_nm_auto(self):
        method = network.address_method("br0", "192.168.0.2", self.ADDR_STATIC,
                                        self.nm({("nmcli", "-g", "GENERAL.CONNECTION", "device", "show", "br0"): "br0",
                                                 ("nmcli", "-g", "ipv4.method", "connection", "show", "br0"): "auto"}))
        self.assertEqual(method, "dhcp")

    def test_no_networkmanager_falls_back_to_kernel(self):
        self.assertEqual(network.address_method("eth0", "192.168.0.2", self.ADDR_STATIC, self.nm({})), "static")

    def test_route_source_and_device(self):
        route = "1.1.1.1 via 192.168.0.1 dev br0 src 192.168.0.2 uid 1000"
        self.assertEqual(network.parse_route_source(route), "192.168.0.2")
        self.assertEqual(network.device_for_address(self.ADDR_STATIC, "192.168.0.2"), "br0")
        self.assertIsNone(network.device_for_address(self.ADDR_STATIC, "10.0.0.9"))


if __name__ == "__main__":
    unittest.main()
