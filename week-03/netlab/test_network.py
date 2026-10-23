"""Regression tests for the Week 3 routed topology and page sections."""
import ipaddress
from pathlib import Path
import unittest

from build_routed import check_paths, check_spec, hosts, load, lookup, plan
from make_page3 import routing_tables_section


ROOT = Path(__file__).resolve().parent


class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load(ROOT / "network.yaml")

    def test_valid_network_and_all_twelve_directed_host_paths(self):
        self.assertEqual(len(self.spec["routers"]), 4)
        self.assertEqual(len(self.spec["lans"]), 4)
        self.assertEqual(len(hosts(self.spec)) * (len(hosts(self.spec)) - 1), 12)
        self.assertEqual(check_spec(self.spec), [])
        self.assertEqual(check_paths(self.spec), [])

    def test_subnets_are_non_overlapping_and_inside_student_block(self):
        nets = [ipaddress.ip_network(lan["network"]) for lan in self.spec["lans"]]
        nets.extend(ipaddress.ip_network(link[2]) for link in self.spec["links"])
        block = ipaddress.ip_network("10.3.0.0/16")
        for i, net in enumerate(nets):
            self.assertTrue(net.subnet_of(block), str(net))
            self.assertFalse(any(net.overlaps(other) for other in nets[i + 1:]), str(net))

    def test_triangle_has_alternate_router_path(self):
        graph = {router: set() for router in self.spec["routers"]}
        for left, right, _ in self.spec["links"]:
            graph[left].add(right)
            graph[right].add(left)
        self.assertIn("r2", graph["r1"])
        graph["r1"].remove("r2")
        graph["r2"].remove("r1")
        seen, pending = set(), ["r1"]
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(graph[node] - seen)
        self.assertIn("r2", seen)

    def test_directly_reachable_next_hops_and_summary_scope(self):
        self.assertEqual(check_spec(self.spec), [])
        r1_h2, h2via = lookup(self.spec, "r1", ipaddress.ip_address("10.3.32.10"))
        r1_h3, h3via = lookup(self.spec, "r1", ipaddress.ip_address("10.3.33.10"))
        self.assertEqual((r1_h2, str(h2via)), ("via", "10.3.12.2"))
        self.assertEqual((r1_h3, str(h3via)), ("via", "10.3.13.2"))
        summary = ipaddress.ip_network("10.3.32.0/20")
        for network in ("10.3.32.0/24", "10.3.33.0/24", "10.3.34.0/24"):
            self.assertTrue(ipaddress.ip_network(network).subnet_of(summary))
        self.assertFalse(ipaddress.ip_network("10.3.1.0/24").subnet_of(summary))
        for destination in ("10.3.32.10", "10.3.33.10", "10.3.34.10"):
            self.assertEqual(lookup(self.spec, "r3", ipaddress.ip_address(destination)),
                             ("via", ipaddress.ip_address("10.3.23.2")))

    def test_missing_route_fixture_is_rejected(self):
        spec = load(ROOT / "missing.yaml")
        self.assertEqual(check_spec(spec), [])
        errors = check_paths(spec)
        self.assertTrue(errors)
        self.assertTrue(any("r2 has no route" in error for error in errors))

    def test_loop_fixture_is_rejected(self):
        spec = load(ROOT / "loop.yaml")
        self.assertEqual(check_spec(spec), [])
        errors = check_paths(spec)
        self.assertTrue(any("loop r2 -> r3 -> r2" in error for error in errors))

    def test_routing_tables_include_four_routers_and_longest_prefix_first(self):
        section = routing_tables_section(self.spec)
        for router in self.spec["routers"]:
            self.assertIn(f"<h3>{router}</h3>", section)
        r1 = section.split('<h3>r1</h3>', 1)[1].split('<h3>r2</h3>', 1)[0]
        self.assertLess(r1.index("10.3.32.0/24"), r1.index("10.3.32.0/20"))


if __name__ == "__main__":
    unittest.main()
