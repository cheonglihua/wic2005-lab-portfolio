# Week 3 — Static Routing and Network Data

This lab extends the portfolio with an IPv4 network built from YAML and tested
in Mininet. It uses the student ID suffix `4903`, so the address block is
`10.3.0.0/16`.

- **Topology:** four routers, four host LANs, and a redundant r1–r2–r3 triangle.
- **Routing:** static routes demonstrate longest-prefix matching and a
  `10.3.32.0/20` summary.
- **Published page:** [Week 3 — Routed Network Lab](https://cheonglihua.github.io/wic2005-lab-portfolio/week3/).

## Contents

1. [Topology and addressing](#1-topology-and-addressing)
2. [Files](#2-files)
3. [Validate and test](#3-validate-and-test)
4. [Run Mininet](#4-run-mininet)
5. [Capture evidence](#5-capture-evidence)
6. [Regenerate and verify the page](#6-regenerate-and-verify-the-page)

## 1. Topology and addressing

Each LAN router uses `.1`, its host uses `.10`; on router links, the first
router named uses `.1` and the second uses `.2`.

| Segment | Network | Addresses |
| --- | --- | --- |
| h1 LAN | `10.3.1.0/24` | r1 `.1`, h1 `.10` |
| r1–r2 | `10.3.12.0/30` | r1 `.1`, r2 `.2` |
| r1–r3 | `10.3.13.0/30` | r1 `.1`, r3 `.2` |
| r3–r2 | `10.3.23.0/30` | r3 `.1`, r2 `.2` |
| r2–r4 | `10.3.24.0/30` | r2 `.1`, r4 `.2` |
| h2 LAN | `10.3.32.0/24` | r2 `.1`, h2 `.10` |
| h3 LAN | `10.3.33.0/24` | r2 `.1`, h3 `.10` |
| h4 LAN | `10.3.34.0/24` | r4 `.1`, h4 `.10` |

### Static routes

| Router | Destination | Next hop |
| --- | --- | --- |
| r1 | `10.3.32.0/24` | `10.3.12.2` |
| r1 | `10.3.32.0/20` | `10.3.13.2` |
| r2 | `10.3.1.0/24` | `10.3.12.1` |
| r2 | `10.3.34.0/24` | `10.3.24.2` |
| r3 | `10.3.1.0/24` | `10.3.13.1` |
| r3 | `10.3.32.0/20` | `10.3.23.2` |
| r4 | `10.3.1.0/24` | `10.3.24.1` |
| r4 | `10.3.32.0/20` | `10.3.24.1` |

The summary covers h2, h3, and h4, but not h1. On r1, the h2 `/24` is more
specific than the `/20`, so h2 uses the direct r1–r2 link while h3 and h4 use
r3. The design has valid forward and return routes for all 12 directed host
pairs.

## 2. Files

| File | Purpose |
| --- | --- |
| `netlab/network.yaml` | Full topology and static routes for the checker and builder |
| `netlab/routes.yaml` | Routes for the interactive Step 10 lab |
| `netlab/build_routed.py` | Validates the data and builds the Mininet network |
| `netlab/routers.py` | Builds the Step 10 topology and applies routes from YAML |
| `netlab/loop.yaml`, `netlab/missing.yaml` | Invalid fixtures for loop and missing-route checks |
| `netlab/test_network.py` | Automated topology, route, and page tests |
| `netlab/make_page3.py`, `netlab/page3.yaml` | Page generator and written reflections |
| `netlab/evidence3/` | Captured Mininet output and validator diagnostics |
| `../docs/week3/index.html` | Generated portfolio page |

## 3. Validate and test

Run these commands in **Windows PowerShell from the repository root**. The
tests and invalid fixtures validate the data without starting Mininet:

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 -m unittest -v
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 build_routed.py loop.yaml
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 build_routed.py missing.yaml
```

The two fixture commands should exit with status 1, print `PROBLEM:` messages,
and end with `nothing was built`. To regenerate `evidence3/check.txt` from the
actual validator CLI:

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 check_routes_evidence.py
```

## 4. Run Mininet

Start the four-router network from PowerShell at the repository root:

```powershell
docker run --rm -it --privileged -v "${PWD}/week-03/netlab:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0 python3 build_routed.py network.yaml
```

Validation runs before the network is built. Use the commands below at the
`mininet>` prompt, one line at a time. The `/lab` mount saves output directly
into `week-03/netlab/evidence3/`.

To run the separate Step 10 route-file workflow instead, launch:

```powershell
docker run --rm -it --privileged -v "${PWD}/week-03/netlab:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0 python3 routers.py --id 4903 --routes routes.yaml
```

## 5. Capture evidence

### Router tables and route lookups

```text
sh echo '== r1 ==' > /lab/evidence3/routes.txt
r1 ip route >> /lab/evidence3/routes.txt
sh echo '== r2 ==' >> /lab/evidence3/routes.txt
r2 ip route >> /lab/evidence3/routes.txt
sh echo '== r3 ==' >> /lab/evidence3/routes.txt
r3 ip route >> /lab/evidence3/routes.txt
sh echo '== r4 ==' >> /lab/evidence3/routes.txt
r4 ip route >> /lab/evidence3/routes.txt

sh echo '== r1 lookup: h2, 10.3.32.10 ==' > /lab/evidence3/lpm.txt
r1 ip route get 10.3.32.10 >> /lab/evidence3/lpm.txt
sh echo '== r1 lookup: h3, 10.3.33.10 ==' >> /lab/evidence3/lpm.txt
r1 ip route get 10.3.33.10 >> /lab/evidence3/lpm.txt

sh echo '== r3 summary lookup: h2, 10.3.32.10 ==' > /lab/evidence3/summary.txt
r3 ip route get 10.3.32.10 >> /lab/evidence3/summary.txt
sh echo '== r3 summary lookup: h3, 10.3.33.10 ==' >> /lab/evidence3/summary.txt
r3 ip route get 10.3.33.10 >> /lab/evidence3/summary.txt
sh echo '== r3 summary lookup: h4, 10.3.34.10 ==' >> /lab/evidence3/summary.txt
r3 ip route get 10.3.34.10 >> /lab/evidence3/summary.txt
```

### Traceroutes and all-pairs connectivity

```text
sh echo '== h1 to h2 ==' > /lab/evidence3/traces.txt
h1 traceroute -n -I -q 1 -m 6 -w 1 10.3.32.10 >> /lab/evidence3/traces.txt
sh echo '== h1 to h3 ==' >> /lab/evidence3/traces.txt
h1 traceroute -n -I -q 1 -m 6 -w 1 10.3.33.10 >> /lab/evidence3/traces.txt
sh echo '== h1 to h4 ==' >> /lab/evidence3/traces.txt
h1 traceroute -n -I -q 1 -m 6 -w 1 10.3.34.10 >> /lab/evidence3/traces.txt

sh echo '== All 12 directed host-pair pings ==' > /lab/evidence3/connectivity.txt
h1 ping -c 1 -W 1 10.3.32.10 >> /lab/evidence3/connectivity.txt
h1 ping -c 1 -W 1 10.3.33.10 >> /lab/evidence3/connectivity.txt
h1 ping -c 1 -W 1 10.3.34.10 >> /lab/evidence3/connectivity.txt
h2 ping -c 1 -W 1 10.3.1.10 >> /lab/evidence3/connectivity.txt
h2 ping -c 1 -W 1 10.3.33.10 >> /lab/evidence3/connectivity.txt
h2 ping -c 1 -W 1 10.3.34.10 >> /lab/evidence3/connectivity.txt
h3 ping -c 1 -W 1 10.3.1.10 >> /lab/evidence3/connectivity.txt
h3 ping -c 1 -W 1 10.3.32.10 >> /lab/evidence3/connectivity.txt
h3 ping -c 1 -W 1 10.3.34.10 >> /lab/evidence3/connectivity.txt
h4 ping -c 1 -W 1 10.3.1.10 >> /lab/evidence3/connectivity.txt
h4 ping -c 1 -W 1 10.3.32.10 >> /lab/evidence3/connectivity.txt
h4 ping -c 1 -W 1 10.3.33.10 >> /lab/evidence3/connectivity.txt
```

### Link-failure and recovery

Run these in order. The traceroute is executed while r1–r2 is still down. The
final commands bring the link and h1-to-h2 route back before `exit`.

```text
sh echo '== Baseline h1 to h2 ==' > /lab/evidence3/failure.txt
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt
sh echo '== Link-down command: link r1 r2 down ==' >> /lab/evidence3/failure.txt
link r1 r2 down
sh echo '== h1 traceroute while r1-r2 is down ==' >> /lab/evidence3/failure.txt
h1 traceroute -n -I -m 5 -w 1 -q 1 10.3.32.10 >> /lab/evidence3/failure.txt 2>&1
sh echo '== r1 lookup for h2 after link down ==' >> /lab/evidence3/failure.txt
r1 ip route get 10.3.32.10 >> /lab/evidence3/failure.txt
sh echo '== r2 lookup for h1 after link down ==' >> /lab/evidence3/failure.txt
r2 ip route get 10.3.1.10 >> /lab/evidence3/failure.txt 2>&1
sh echo '== h1 to h2 after link down ==' >> /lab/evidence3/failure.txt
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt 2>&1
sh echo '== Link-restoration command: link r1 r2 up ==' >> /lab/evidence3/failure.txt
link r1 r2 up
sh echo '== r2 table after link restoration ==' >> /lab/evidence3/failure.txt
r2 ip route >> /lab/evidence3/failure.txt
sh echo '== h1 to h2 after link restoration, before route repair ==' >> /lab/evidence3/failure.txt
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt 2>&1
sh echo '== r2 lookup for h1 before manual route repair ==' >> /lab/evidence3/failure.txt
r2 ip route get 10.3.1.10 >> /lab/evidence3/failure.txt 2>&1
sh echo '== Manually restore r2 route to h1 ==' >> /lab/evidence3/failure.txt
r2 ip route add 10.3.1.0/24 via 10.3.12.1
r2 ip route get 10.3.1.10 >> /lab/evidence3/failure.txt
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt
exit
```

The captured trace shows the hops that reply and any `*` timeouts. The route
lookups and pings show forward and return-path behavior; static routes do not
recalculate after a link change, so the missing route must be restored manually.

## 6. Regenerate and verify the page

After all evidence files are saved, regenerate the page from PowerShell at the
repository root:

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 make_page3.py network.yaml
```

The generator validates the topology and host paths before writing
`docs/week3/index.html`. After the `Deploy portfolio site` GitHub Actions run
succeeds, check the published page in PowerShell:

```powershell
(Invoke-WebRequest -Uri "https://cheonglihua.github.io/wic2005-lab-portfolio/week3/?verify=1" -UseBasicParsing).StatusCode
```

The expected status is `200`. The page should show four routers and expandable
topology, routing-table, evidence, and reflection sections.
