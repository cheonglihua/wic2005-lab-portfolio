#!/usr/bin/env python3
"""Validate a YAML/JSON topology description, then build it in Mininet."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required (it is included in the course container).") from exc
    with path.open(encoding="utf-8") as source:
        try:
            data = yaml.safe_load(source)
        except yaml.YAMLError as exc:
            raise ValueError(f"{path}: malformed YAML/JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("topology must be a mapping with switches, hosts, and links")
    return data


def check(data: dict[str, Any]) -> list[str]:
    """Return all detected problems; an empty list means the description is valid."""
    problems: list[str] = []
    suffix = data.get("student_id_last4")
    if not isinstance(suffix, str) or not re.fullmatch(r"\d{4}", suffix):
        problems.append("student_id_last4 must contain exactly four digits")
        suffix = "0000"
    nn = int(suffix[-2:])
    ipv4_block = ipaddress.ip_network(f"10.{nn}.0.0/16")
    ipv6_block = ipaddress.ip_network(f"fd00:{suffix}::/32")

    switches = data.get("switches")
    hosts = data.get("hosts")
    links = data.get("links")
    if not isinstance(switches, list):
        problems.append("switches must be a list")
        switches = []
    if not isinstance(hosts, list):
        problems.append("hosts must be a list")
        hosts = []
    if not isinstance(links, list):
        problems.append("links must be a list")
        links = []

    names: set[str] = set()
    for switch in switches:
        if not isinstance(switch, str) or not switch:
            problems.append(f"invalid switch name: {switch!r}")
        elif switch in names:
            problems.append(f"duplicate node name: {switch}")
        else:
            names.add(switch)

    addresses: dict[str, str] = {}
    for host in hosts:
        if not isinstance(host, dict) or not isinstance(host.get("name"), str) or not host["name"]:
            problems.append(f"invalid host entry: {host!r}")
            continue
        name = host["name"]
        if name in names:
            problems.append(f"duplicate node name: {name}")
        names.add(name)
        for key, block in (("ip", ipv4_block), ("ipv6", ipv6_block)):
            value = host.get(key)
            if not isinstance(value, str) or "N" in value:
                problems.append(f"{name} has a missing or placeholder {key} address")
                continue
            try:
                interface = ipaddress.ip_interface(value)
            except ValueError:
                problems.append(f"{name} has an invalid {key} address: {value}")
                continue
            expected_version = 4 if key == "ip" else 6
            if interface.version != expected_version or interface.ip not in block:
                problems.append(f"{name} address {value} is outside its assigned block {block}")
                continue
            address = str(interface.ip)
            if address in addresses:
                problems.append(f"{name} and {addresses[address]} both use {address}")
            else:
                addresses[address] = name

    for link in links:
        if not isinstance(link, list) or len(link) != 2 or not all(isinstance(node, str) for node in link):
            problems.append(f"invalid link entry: {link!r}")
            continue
        for node in link:
            if node not in names:
                problems.append(f"link {link[0]}-{link[1]} names unknown node {node}")
        if link[0] == link[1]:
            problems.append(f"link cannot connect a node to itself: {link[0]}")
    return problems


def build(data: dict[str, Any]) -> None:
    # Imports are delayed so --check-only can also be used on a laptop without Mininet.
    try:
        from mininet.cli import CLI
        from mininet.net import Mininet
        from mininet.node import Host
        from mininet.nodelib import LinuxBridge
    except ImportError as exc:
        raise RuntimeError("Mininet is required; run this script inside the course container.") from exc

    net = Mininet(controller=None, build=False)
    try:
        for switch in data["switches"]:
            net.addSwitch(switch, cls=LinuxBridge)
        for host in data["hosts"]:
            net.addHost(host["name"], cls=Host, ip=host["ip"])
        for left, right in data["links"]:
            net.addLink(left, right)
        net.build()
        net.start()
        for host in data["hosts"]:
            net.get(host["name"]).cmd(
                f"ip -6 addr add {host['ipv6']} dev {host['name']}-eth0"
            )
        # Let IPv6 Duplicate Address Detection finish before the CLI is ready.
        time.sleep(3)
        CLI(net)
    finally:
        net.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topology", type=Path, help="YAML or JSON topology file")
    parser.add_argument("--check-only", action="store_true", help="validate without starting Mininet")
    args = parser.parse_args()
    try:
        data = load(args.topology)
        problems = check(data)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"PROBLEM: {exc}")
        return 1
    if problems:
        for problem in problems:
            print(f"PROBLEM: {problem}")
        return 1
    print(f"OK: {args.topology} passed validation")
    if not args.check_only:
        build(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
