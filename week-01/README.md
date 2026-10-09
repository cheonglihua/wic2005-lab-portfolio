# Week 1 - Why Programmable Networks Exist

## Objective

Build a small Ethernet network and observe what happens when the data plane
learns by itself. The topology has three hosts connected to one Linux bridge:

```text
h1 (10.0.0.1) --\
h2 (10.0.0.2) ---- s1 (Linux bridge)
h3 (10.0.0.3) --/
```

There is no SDN controller and no manually installed flow configuration. This
is the baseline that later programmable-network designs change.

## Prerequisites

- Docker Desktop on Windows or macOS, or Docker Engine on Linux.
- A terminal with access to this repository.
- Internet access the first time the course image is downloaded.

Check Docker before starting:

```powershell
docker run hello-world
```

## Reproduce the lab

From the repository root, run:

```powershell
.\week-01\run_lab.ps1
```

The script starts `firdaussahran/netlab-mininet:1.0`, creates the topology,
runs the observations, and writes the complete terminal transcript to
`week-01\results.txt`. The container is removed when the run finishes.

The equivalent interactive command is:

```powershell
docker run -it --rm --privileged -v "${PWD}:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0
```

Then, inside the container:

```text
mn --topo single,3 --mac --switch lxbr --controller none
```

## Observations and results

### 1. Topology and addressing

`nodes`, `net`, and `dump` show three hosts and one switch:

- `h1` is `10.0.0.1` on `s1-eth1`.
- `h2` is `10.0.0.2` on `s1-eth2`.
- `h3` is `10.0.0.3` on `s1-eth3`.
- `s1` is a Linux bridge, not an OpenFlow-controlled switch.

### 2. Before traffic

Before a host sends traffic, `h1 ip neigh` has no entry for `h2`, and
`brctl showmacs s1` does not yet contain the three Mininet host MAC addresses.
The bridge cannot have learned a source MAC address until it has seen a frame
from that host.

### 3. ARP and bridge learning

After:

```text
h1 ping -c 3 h2
```

the ping succeeds with 0% packet loss. ARP resolves `10.0.0.2` to
`00:00:00:00:00:02`, and the bridge learns:

```text
00:00:00:00:00:01 -> port 1
00:00:00:00:00:02 -> port 2
00:00:00:00:00:03 -> port 3
```

The exact bridge output also includes dynamically generated local bridge MAC
addresses, so those values can differ between runs. Host MAC addresses remain
predictable because the `--mac` option is used.

`h3` was not present in the first learned host entries because it had not sent
traffic yet. Running `pingall` causes every host to exchange traffic and all
three host MAC addresses then appear in the bridge table.

### 4. Link failure and recovery

With:

```text
link s1 h3 down
pingall
```

traffic involving `h3` fails, while `h1` and `h2` can still communicate. The
observed result is 66% dropped (2 of 6 host-to-host tests succeed). After:

```text
link s1 h3 up
pingall
```

all six tests succeed again with 0% dropped. No controller or manual route
change is needed: restoring the data-plane link restores connectivity.

### 5. Application traffic

Finally, `h2` serves a directory listing with Python's built-in HTTP server,
and `h1` retrieves it with `curl`. This confirms that the bridge carries
ordinary application traffic, not only ICMP:

```text
h2 python3 -m http.server 80 &
sh sleep 1
h1 curl -sS h2
```

## Why this matters

The bridge learns from source MAC addresses and forwards known destinations
only to the corresponding port. Unknown or broadcast traffic is flooded so
that the destination can reply. This is control-plane-free Ethernet learning:
the switch data plane uses observations from frames rather than a controller
or a human configuration session.

The experiment also shows the limits of this baseline. It provides local
Layer-2 connectivity, but it does not give a network-wide policy, automation,
or a programmable packet-processing pipeline. Those are the motivations for
the programmable-network approaches covered later in the course.

## Files

- [`run_lab.ps1`](./run_lab.ps1) - reproducible Docker/Mininet run.
- [`results.txt`](./results.txt) - generated transcript; run the script to
  recreate it.
