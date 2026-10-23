#!/usr/bin/env python3
"""Show check_paths() rejecting a missing route and a forwarding loop."""
from copy import deepcopy
from pathlib import Path

from build_routed import check_paths, load


SPEC = load(Path(__file__).with_name("network.yaml"))

missing = deepcopy(SPEC)
missing["routes"]["r2"] = []
print("Missing-route case:")
for problem in check_paths(missing):
    print("PROBLEM:", problem)

loop = deepcopy(SPEC)
# For h2 -> h1, send r2 to r3 and r3 back to r2.
loop["routes"]["r2"] = [{"to": "10.3.1.0/24", "via": "10.3.23.1"}]
loop["routes"]["r3"] = [
    route for route in loop["routes"]["r3"] if route["to"] != "10.3.1.0/24"
]
loop["routes"]["r3"].append({"to": "10.3.1.0/24", "via": "10.3.23.2"})
print("\nLoop case:")
for problem in check_paths(loop):
    print("PROBLEM:", problem)
