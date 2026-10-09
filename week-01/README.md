# Week 1 - Why Programmable Networks Exist

## Published web page

Read the visual version of this write-up at:

https://cheonglihua.github.io/ID_REDACTED_wic2005-lab-portfolio/

This link is permanent for the repository. It will serve the latest committed
version whenever GitHub Pages is enabled with **GitHub Actions** and the
**Deploy portfolio site** workflow completes successfully.

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

Open PowerShell and first change to the repository root. This matters because
the interactive Docker command mounts the current directory into `/lab`:

```powershell
Set-Location C:\ID_REDACTED_wic2005-lab-portfolio
```

The recommended reproducible run is:

```powershell
.\week-01\run_lab.ps1
```

The script starts the pinned image `firdaussahran/netlab-mininet:1.0`,
creates the topology, runs the observations, and writes the complete terminal
transcript to `week-01\results.txt`. The container is removed when the run
finishes.

The equivalent interactive command is:

```powershell
docker run -it --rm --privileged -v "${PWD}:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0
```

Do not run the command from `C:\Windows\System32` or another system
directory. The `h2` web server serves its current directory, so doing that
would expose a system-directory listing in the lab output. The script avoids
this mistake by always mounting this repository's directory.

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

Immediately after startup, `h1 ip neigh` normally has no entry for `h2`.
The bridge MAC table can be empty or can already contain host MAC addresses,
depending on frames exchanged during startup and the age of entries from the
bridge. The important point is that the bridge learns source MAC addresses
from observed Ethernet frames; it does not receive a manually configured
forwarding table.

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
traffic yet in that observation. In some runs, startup traffic may already
populate one or more entries. Running `pingall` causes every host to exchange
traffic and all three host MAC addresses then appear in the bridge table.

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

## Interpreting terminal messages

The image may print `Error setting resource limits` and warnings about
`bridge-nf-call-*`. These are expected in Docker Desktop and do not prevent
the lab from running. Use the commands exactly as shown in this report:
Mininet treats mistyped input as a shell command, which can produce messages
such as `hping: command not found` or `No such device` even though the
topology itself is healthy. For example, the switch is named `s1`, so use
`brctl showmacs s1`, not `brctl showmacs s`.
