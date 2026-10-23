# Week 3 evidence

These captures were collected from `build_routed.py network.yaml` running in
the course Mininet Docker image. They use the `10.3.x.x` addresses in the final
four-router topology.

- `routes.txt`: `ip route` from r1, r2, r3 and r4.
- `lpm.txt`: r1 sends h2 through the /24 on r1–r2 and h3 through the /20 via r3.
- `summary.txt`: r3 sends lookups for h2, h3 and h4 to `10.3.23.2`.
- `traces.txt`: real ICMP traceroutes from h1 to h2, h3 and h4.
- `connectivity.txt`: one successful ping for each of the 12 directed host pairs.
- `failure.txt`: baseline, r1–r2 outage, actual h1 traceroute while the link is
  down, alternate forward lookup, missing return route, link restoration and
  successful manual route recovery. The trace records hops 1 and 2, then timeouts
  while the return route is missing.
- `check.txt`: actual CLI output rejecting the loop and missing-route fixtures
  before Mininet builds anything.

To reproduce captures, follow the exact Docker and `mininet>` command sequence
in [`../../README.md`](../../README.md). `check_routes_evidence.py` regenerates
`check.txt` by invoking the actual `build_routed.py` CLI against each fixture.
