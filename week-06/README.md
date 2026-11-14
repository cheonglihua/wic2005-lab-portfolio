# Week 6 — Virtualisation, Overlays and Software Forwarding

This week looks under Mininet, then builds a multi-tenant VXLAN data centre from
YAML. The address block comes from the student ID suffix `4903`: IPv4
`10.3.0.0/16`, IPv6 `fd00:4903::/32`.

- **Assignment:** Overlay your own data centre
- **Published page:** [Week 6: my data centre overlay](https://cheonglihua.github.io/wic2005-lab-portfolio/week6/)
- **Assignment files:** [`netlab/`](./netlab/)
- **Lab transcripts:** [`lab/results/`](./lab/results/)

## Contents

1. [Files](#1-files)
2. [How to rerun](#2-how-to-rerun)
3. [Lab answers](#3-lab-answers)
4. [AI use](#ai-use)

## 1. Files

| File | Purpose |
| --- | --- |
| `netlab/overlay.yaml` | My design: 4 racks, tenants shop/bank (overlapping `10.3.50.0/24`) and lab; MTU fix B |
| `netlab/blackhole.yaml` | The same design with all MTUs at 1500: refused by `check_mtu()` |
| `netlab/mtu_a.yaml`, `netlab/mtu_b.yaml` | Fix A (tenants 1450) and fix B (underlay 9000) |
| `netlab/build_overlay.py` | Builder; my `tenant_commands()` and `check_mtu()` |
| `netlab/make_page6.py`, `netlab/page6.yaml` | Page generator and my answers |
| `netlab/cli/*.cli` | The `mininet>` commands used to collect each evidence file (`probe.cli` was a quick size sweep to find the black-hole limit before recording it) |
| `netlab/evidence6/` | Evidence: check, connectivity, flood, isolation, black hole, fixes |
| `lab/*.cmds`, `lab/part2.sh` | Lab Parts 1–6 commands with my addresses |
| `lab/results/` | Lab transcripts, Parts 1–7 |
| `../docs/week6/index.html` | Generated page |

## 2. How to rerun

From PowerShell in the repository root. The interactive build is the same as in
the assignment:

```powershell
docker run --rm -it --privileged -v "${PWD}/week-06/netlab:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0 python3 build_overlay.py overlay.yaml
```

At the `mininet>` prompt, `source cli/connectivity.cli` (or any other script in
`cli/`) replays the evidence commands. Use a fresh network for each script, in
this order: `flood_isolation.cli` on `overlay.yaml`,
`blackhole.cli` on `blackhole.yaml --force`, `fix_a.cli` on `mtu_a.yaml`, then
`fix_b.cli` on `mtu_b.yaml`.

`check_mtu()` refusing the black-hole design:

```powershell
docker run --rm -v "${PWD}/week-06/netlab:/lab" -w /lab `
  firdaussahran/netlab-mininet:1.0 python3 build_overlay.py blackhole.yaml
```

Regenerate the page straight into `docs/week6/`:

```powershell
docker run --rm -v "${PWD}/week-06/netlab:/lab" -v "${PWD}/docs:/lab/docs" -w /lab `
  firdaussahran/netlab-mininet:1.0 python3 make_page6.py overlay.yaml
```

## 3. Lab answers

### Linux building blocks behind a Mininet host and cable

A Mininet **host** is a `bash` process in its own **network namespace**. In
[Part 1](./lab/results/part1.txt), `dump` gives h1 `pid=17` and h2 `pid=19`,
and `lsns -t net` lists exactly those PIDs, each with its own namespace
(`4026532574`, `4026532672`). A Mininet **cable** is a **veth pair**. Inside h1
there is only `h1-eth0@if3`. Its peer, `s1-eth1`, is in the root namespace and
is a port of the Linux **bridge** `s1`. In
[Part 2](./lab/results/part2.txt) I built the same thing by hand with
`ip netns`, `ip link add … type veth` and `ip link add br0 type bridge`.
`red` pinged `blue` (`10.3.9.1` → `10.3.9.2`), and `br0` learned both veth
MACs.

### MTU and throughput, underlay and overlay

From [Parts 4–5](./lab/results/part3-6.txt):

| Measurement | Underlay (`h1-eth0`) | VXLAN over IPv4 (`vxlan100`) | VXLAN over IPv6 (`vxlan106`) |
| --- | --- | --- | --- |
| Interface MTU | 1500 | 1450 | 1430 |
| Largest DF ping that works | n/a | `-s 1422` (1450) | `-s 1402` (1430) |
| First that fails | n/a | `-s 1423`: `message too long, mtu=1450` | `-s 1403`: `message too long, mtu=1430` |
| iperf3 receiver | **29.1 Gbit/s** | **16.3 Gbit/s** (56% of underlay) | not measured |

The 50 bytes, header by header, as each inner packet is wrapped:

- inner Ethernet header, **14** bytes: the tenant's frame is carried whole as payload;
- VXLAN header, **8** bytes: flags and the 24-bit VNI;
- UDP header, **8** bytes: destination port 4789;
- outer IPv4 header, **20** bytes: from VTEP `10.3.0.1` to `10.3.0.2`.

14 + 8 + 8 + 20 = 50, so 1500 − 50 = 1450. The outer Ethernet header is not
counted, because MTU limits the IP packet, not the frame. Over IPv6 the outer
IP header is **40** bytes instead of 20, so the cost is 70 and the tunnel MTU is
1430. The Part 5 capture shows the same `vni 106` packets between
`fd00:4903::1` and `fd00:4903::2`.

### Why small pings worked during the MTU mismatch but TCP almost stopped

With `h2-eth0` at MTU 1400, an encapsulated packet reaches h2 only if it is at
most 1404 bytes (1400 plus the 4-byte VLAN allowance). The limit I found was
`-s 1326` working and `-s 1327` lost: 1326 + 28 + 50 = 1404. A small ping is
84 + 50 = 134 bytes, so it always fits. TCP, however, fills each segment to
h1's MSS, which comes from `vxlan100`'s MTU of 1450. h1 has no idea that h2's
side is smaller.

Every full segment becomes a 1500-byte outer packet and is dropped as it
arrives. `s1-eth2 tx_dropped` and `h2-eth0 rx_dropped` both went from 9 to 13
after three large pings. The drop happens at layer 2, so no ICMP "fragmentation
needed" comes back, and Path MTU Discovery never learns the limit. TCP keeps
retransmitting the same oversized segments. Only small packets get through, so
throughput fell to **629 Kbit/s**. After `h2 ip link set h2-eth0 mtu 1500` it
was back to 15.3 Gbit/s. Linux would not let me raise `vxlan100` to 1500
(`RTNETLINK answers: Invalid argument`), because it checks the tunnel against
its own underlay. It cannot check a device elsewhere on the path.

### What a Docker container has that a Mininet host doesn't

From [Part 7](./lab/results/part7.txt): the container also has a network
namespace and a veth (`eth0@if82`, `172.17.0.2/16` on Docker's bridge). It has
more besides:

- its own **filesystem image**: `/etc/os-release` says Alpine Linux v3.20;
- its own **PID namespace**: `ps` shows only `sleep 600` as PID 1, plus `ps` itself;
- its own mount, UTS (hostname) and IPC namespaces, and cgroup resource limits.

A Mininet host shares the filesystem, the process table and everything else
with the machine it runs on. Only its network is separate.

### This VXLAN tunnel compared with the Week 5 P4 tunnel

As the lecture's `vtep.p4` puts it, Week 5's tunnel "added one small header that
every switch had to understand". The 4-byte figure below assumes the P4
`basic_tunnel` header (`proto_id` + `dst_id`).

| | VXLAN (this lab) | Week 5 P4 tunnel |
| --- | --- | --- |
| Bytes added | 50 over IPv4, 70 over IPv6 | 4 (`proto_id` + `dst_id`) |
| Devices that must understand it | Only the two VTEPs. `s1` forwarded ordinary UDP/IP to port 4789 without knowing about the tunnel. | Every switch on the path must parse the tunnel header and have a table entry for its `dst_id` |
| What stops a loop | The outer IPv4/IPv6 header has a TTL/hop limit that underlay routers decrement. The underlay's own loop prevention also applies. | The tunnel header has no TTL, and tunnel forwarding does not decrement the inner IP TTL. Only correct table entries prevent a loop. |

VXLAN pays more bytes to run over any existing IP network. The P4 tunnel is
cheap, but it needs a programmable switch at every hop.

## AI use

**Declared level: Level 3 (Open).**

I used Claude Code to assist with code development and ChatGPT to review
networking concepts, check technical explanations and improve the clarity of
my written answers. I reviewed the suggestions, verified the implementation
through Mininet experiments and used the actual test outputs as evidence. I
remain responsible for the submitted work and can explain the design,
configurations and experimental results.
