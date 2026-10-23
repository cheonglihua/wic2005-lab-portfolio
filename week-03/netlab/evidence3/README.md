# Week 3 evidence

Save real outputs from the course Mininet container here. Do not replace them
with predicted output. Start Mininet from the repository root using the
`routers.py` command in `../../README.md`.

At the `mininet>` prompt, capture the three route tables and representative
forwarding decisions:

```text
r1 ip route > /lab/evidence3/routes.txt
r2 ip route >> /lab/evidence3/routes.txt
r3 ip route >> /lab/evidence3/routes.txt
r1 ip route get 10.3.32.10 > /lab/evidence3/summary.txt
r1 ip route get 10.3.33.10 >> /lab/evidence3/summary.txt
h1 traceroute -n -m 5 -w 1 10.3.32.10 > /lab/evidence3/traces.txt
h1 traceroute -n -m 5 -w 1 10.3.33.10 >> /lab/evidence3/traces.txt
h2 traceroute -n -m 5 -w 1 10.3.1.10 >> /lab/evidence3/traces.txt
link r1 r2 down
h1 ping -c 2 -W 1 10.3.32.10 > /lab/evidence3/failure.txt
h1 traceroute -n -m 5 -w 1 10.3.32.10 >> /lab/evidence3/failure.txt
r1 ip route get 10.3.32.10 >> /lab/evidence3/failure.txt
r2 ip route get 10.3.1.10 >> /lab/evidence3/failure.txt 2>&1
link r1 r2 up
sh echo 'After bringing r1-r2 back up:' >> /lab/evidence3/failure.txt
r2 ip route >> /lab/evidence3/failure.txt
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt
r2 ip route add 10.3.1.0/24 via 10.3.12.1
h1 ping -c 2 -W 1 10.3.32.10 >> /lab/evidence3/failure.txt
exit
```

The output records the failed ping after the link comes back up and its success
after manually restoring r2's static route. If `traceroute` is not installed
in the image, record that and use the available `tracepath` command. The
Mininet bind mount writes these files directly into this folder.

To capture `check_paths()` rejecting a loop and a missing route, run this
from the repository root in PowerShell. It uses the container's Python and
Mininet dependencies but does not start a network:

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo `
  firdaussahran/netlab-mininet:1.0 `
  python3 week-03/netlab/check_routes_evidence.py `
  > week-03/netlab/evidence3/check.txt
```

This runs the validator against two modified copies of the data and records
its diagnostics; it does not change `network.yaml` or build Mininet.
