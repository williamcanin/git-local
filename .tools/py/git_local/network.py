"""LAN address (fixed or DHCP), the mDNS name, and the firewall reminder.

The installer never changes firewall rules; warn_lan_ports only says which ports
the local network needs (examples are in README.md).
"""

from __future__ import annotations

import os
import re
import sys
from typing import Callable

from .paths import GIT_HOST, LAN_PORT, SSH_PORT
from .state import State
from .util import die, log, output, warn

ADDR_LINE = re.compile(r"\binet (\S+)/\d+ ")


def address_method(dev: str, ip: str, addr_output: str, nm: Callable[[list[str]], str]) -> str:
    """'static' or 'dhcp' for an address on a device.

    The kernel marks a DHCP address as 'dynamic'. NetworkManager also records the
    IPv4 method of the device's connection ('auto' = DHCP, 'manual' = fixed).
    """
    for line in addr_output.splitlines():
        match = ADDR_LINE.search(line)
        if match and match.group(1) == ip and " dynamic" in line:
            return "dhcp"

    profile = nm(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", dev])
    if profile and nm(["nmcli", "-g", "ipv4.method", "connection", "show", profile]) == "auto":
        return "dhcp"
    return "static"


def parse_route_source(route_output: str) -> str | None:
    fields = route_output.split()
    for index, field_value in enumerate(fields[:-1]):
        if field_value == "src":
            return fields[index + 1]
    return None


def device_for_address(addr_output: str, ip: str) -> str | None:
    for line in addr_output.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[3].split("/")[0] == ip:
            return fields[1]
    return None


def address_from_network(state: State) -> None:
    """Detect the LAN address (GIT_LOCAL_IP overrides) and report if it is DHCP."""
    ip = os.environ.get("GIT_LOCAL_IP", "").strip()
    if not ip:
        ip = parse_route_source(output(["ip", "-4", "route", "get", "1.1.1.1"])) or ""
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip):
        die("Could not detect this computer's LAN address. Set GIT_LOCAL_IP, for example: GIT_LOCAL_IP=192.168.0.2 make install")
    state.lan_ip = ip

    dev = device_for_address(output(["ip", "-4", "-o", "addr", "show"]), ip)
    if dev is None:
        warn(f"{ip} is not assigned to this computer. Clients will not reach the server at this address.")
        return

    dev_addr = output(["ip", "-4", "-o", "addr", "show", "dev", dev])
    if address_method(dev, ip, dev_addr, output) == "dhcp":
        warn(f"{ip} on {dev} comes from DHCP and may change. Clients (phones, other computers) will break if it changes.")
        print("    Set a fixed address on this computer, or reserve it in the router DHCP settings,", file=sys.stderr)
        print("    then run make install again.\n", file=sys.stderr)
    else:
        log(f"git.local will be announced as {ip} (static address on {dev})")


def warn_lan_ports(state: State) -> None:
    subnet = ".".join(state.lan_ip.split(".")[:3]) + ".0/24"
    warn(f"The firewall on this computer must allow TCP ports 80 and 443 (git.local), {LAN_PORT} (phones, HTTPS) and {SSH_PORT} (Git over SSH) from {subnet}.")
    print('    The installer does not change firewall rules. Add them yourself; examples are in README.md ("Firewall").\n', file=sys.stderr)


def check_mdns_conflict(state: State) -> None:
    fields = output(["timeout", "5", "avahi-resolve", "-4", "-n", GIT_HOST]).split()
    resolved = fields[1] if len(fields) >= 2 else ""
    if resolved != state.lan_ip:
        warn(f"{GIT_HOST} resolves to '{resolved or 'nothing'}' on the network, not {state.lan_ip}. Another computer may announce the same name.")
    else:
        log(f"{GIT_HOST} is announced on the network as {state.lan_ip}")
