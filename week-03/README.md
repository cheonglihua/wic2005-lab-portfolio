# Week 3 — Static Routing and Network Data

The routed lab uses student suffix `4903`, giving the IPv4 block `10.3.0.0/16`.
It has four routers, four host LANs and the redundant r1–r2–r3 triangle. Router
r4 extends the topology from r2 over a separate /30 link.

## Topology and routes

| Segment | Network | Endpoints |
| --- | --- | --- |
| h1 LAN | `10.3.1.0/24` | r1 `.1`, h1 `.10` |
| r1–r2 | `10.3.12.0/30` | r1 `.1`, r2 `.2` |
| r1–r3 | `10.3.13.0/30` | r1 `.1`, r3 `.2` |
| r3–r2 | `10.3.23.0/30` | r3 `.1`, r2 `.2` |
| r2–r4 | `10.3.24.0/30` | r2 `.1`, r4 `.2` |
| h2 LAN | `10.3.32.0/24` | r2 `.1`, h2 `.10` |
| h3 LAN | `10.3.33.0/24` | r2 `.1`, h3 `.10` |
| h4 LAN | `10.3.34.0/24` | r4 `.1`, h4 `.10` |

Static routes preserve the h2 longest-prefix demonstration: r1 has
`10.3.32.0/24 via 10.3.12.2` and the broader `10.3.32.0/20 via 10.3.13.2`.
r3 sends that /20 summary toward r2 (`10.3.23.2`). r2 routes h1 through r1 and
h4 through r4. r4 sends h1 and the /20 LAN block toward r2. This yields a valid
forward and return path for all 12 directed host pairs.

## Files

- `netlab/network.yaml` — topology and complete static routing data.
- `netlab/routes.yaml` — equivalent Step 10 routes data.
- `netlab/routers.py` — interactive Step 10 lab builder and route validator.
- `netlab/build_routed.py` — YAML validation, path checking and Mininet builder.
- `netlab/loop.yaml`, `netlab/missing.yaml` — intentionally invalid fixtures.
- `netlab/test_network.py` — automated validator, route lookup and page tests.
- `netlab/make_page3.py`, `netlab/page3.yaml` — generated page and reflections.
- `netlab/evidence3/` — live Mininet output and actual validator diagnostics.
- `../docs/week3/index.html` — generated portfolio page.

## Validate and test (PowerShell)

From the repository root, use the course image for the required PyYAML and
Mininet dependencies. Validation runs before Mininet is started:

```powershell
docker run --rm -it --privileged -v "${PWD}/week-03/netlab:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0 python3 build_routed.py network.yaml
```

At the resulting Mininet prompt, `exit` stops the lab. To validate only, run
the automated tests and invalid fixtures (these commands do not create a
network):

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 -m unittest -v
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 build_routed.py loop.yaml
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 build_routed.py missing.yaml
```

The separate Step 10 route-file workflow can also be started with:

```powershell
docker run --rm -it --privileged -v "${PWD}/week-03/netlab:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0 python3 routers.py --id 4903 --routes routes.yaml
```

The two fixture commands should exit with status 1, report a `PROBLEM:`, and
end with `nothing was built`. To record their actual program output:

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 check_routes_evidence.py
```

## Run Mininet and capture live evidence

Use this from the repository root. The mounted folder keeps the captured files
in the working tree:

```powershell
docker run --rm -it --privileged -v "${PWD}/week-03/netlab:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0 python3 build_routed.py network.yaml
```

At the `mininet>` prompt, enter the following commands **one line at a time**.
Each `sh echo` writes a label to the corresponding capture file.

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
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt
sh echo '== Link restoration command: link r1 r2 up ==' >> /lab/evidence3/failure.txt
link r1 r2 up
sh echo '== r2 table after link restoration ==' >> /lab/evidence3/failure.txt
r2 ip route >> /lab/evidence3/failure.txt
sh echo '== h1 to h2 after link restoration, before route repair ==' >> /lab/evidence3/failure.txt
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt
sh echo '== Manually restore r2 return route ==' >> /lab/evidence3/failure.txt
r2 ip route add 10.3.1.0/24 via 10.3.12.1
r2 ip route get 10.3.1.10 >> /lab/evidence3/failure.txt
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt
exit
```

These commands restore the link and the missing return route before exiting.
Inspect the observed results and update the failure reflection if they differ
from the current notes.

## Regenerate and verify the page

After all seven evidence files are populated, run from the repository root:

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo/week-03/netlab `
  firdaussahran/netlab-mininet:1.0 python3 make_page3.py network.yaml
```

The generator validates the data and all host paths before writing
`docs/week3/index.html`. The published page is
[Week 3 — Routed Network Lab](https://cheonglihua.github.io/wic2005-lab-portfolio/week3/).
After the `Deploy portfolio site` GitHub Actions run succeeds, check the live
response in PowerShell (the query parameter avoids an old cached copy):

```powershell
(Invoke-WebRequest -Uri "https://cheonglihua.github.io/wic2005-lab-portfolio/week3/?verify=1" -UseBasicParsing).StatusCode
```

The expected status is `200`; the page should show four routers and include the
expanded connectivity, LPM, summary-route and failure evidence.
