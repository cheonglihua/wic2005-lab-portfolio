# Week 3 — Static Routing and Network Data

This lab extends the portfolio's data-driven network work into IPv4 routing.
The design uses the last four student ID digits already recorded in Week 2
(`4903`), so its address block is `10.3.0.0/16`.

## Design

Three routers form a triangle: r1 connects directly to r2 and also reaches r2
through r3. Host h1 is on r1's LAN; h2 and h3 use separate LANs on r2. The
specific route on r1 sends the h2 LAN over the direct link, while a `/20`
summary reaches the r2 LAN block through r3. The r3 route sends that summary to
r2. This gives us a concrete way to compare longest-prefix matching with
static-route behavior when a link fails.

## Files

- `netlab/network.yaml` — complete three-router topology and static routes.
- `netlab/routes.yaml` — the Step 4 routes in a separate data file.
- `netlab/routers.py` — the supplied Step 10 lab, including route validation.
- `netlab/build_routed.py` — topology checker and Mininet builder.
- `netlab/make_page3.py` and `netlab/page3.yaml` — page generator and written
  reflections.
- `netlab/evidence3/` — captured route tables, traceroutes, route lookups,
  link-failure results, and route-checker diagnostics.
- `../docs/week3/index.html` — generated portfolio page.

## Week 3 page

[Open the Week 3 routed network page](https://cheonglihua.github.io/wic2005-lab-portfolio/week3/).

## Run in the course container

From the repository root in PowerShell, start the first lab with the routes
file:

```powershell
docker run --rm -it --privileged -v "${PWD}/week-03/netlab:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0 `
  python3 routers.py --id 4903 --routes routes.yaml
```

At the Mininet prompt, inspect routes and test the hosts:

```text
r1 ip route
r2 ip route
r3 ip route
h1 ping -c 2 10.3.32.10
h1 ping -c 2 10.3.33.10
h2 ping -c 2 10.3.1.10
```

Type `exit` to close it. To build the topology directly from the complete
network description, run this instead:

```powershell
docker run --rm -it --privileged -v "${PWD}:/repo" -w /repo `
  firdaussahran/netlab-mininet:1.0 `
  python3 week-03/netlab/build_routed.py week-03/netlab/network.yaml
```

## Collect evidence and publish the page

Follow [`netlab/evidence3/README.md`](netlab/evidence3/README.md) to capture
outputs from Mininet. The evidence folder starts empty; the page generator
will mark any missing evidence. Once the live outputs are saved, generate the
page from the repository root:

```powershell
docker run --rm -v "${PWD}:/repo" -w /repo `
  firdaussahran/netlab-mininet:1.0 `
  python3 week-03/netlab/make_page3.py week-03/netlab/network.yaml
```

The generated page is `docs/week3/index.html`. It includes the captured live
evidence and the observed failure/recovery behavior. The generator checks the
topology and all host-to-host routes before it writes the page.
