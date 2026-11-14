#!/usr/bin/env python3
"""Week 6 assignment: generate your overlay's page from overlay.yaml.

Run it in the course container, from your netlab folder:
    python3 make_page6.py overlay.yaml

It checks overlay.yaml with the same checks as build_overlay.py (including your check_mtu()),
so a design that would black-hole big packets never gets published, then writes
docs/week6/index.html with your design, the VTEP commands your tenant_commands() produces for
every hypervisor, your evidence (evidence6/) and your answers (page6.yaml).
GitHub Pages publishes it at https://<you>.github.io/<repository>/week6/

The checks, the commands and the data block are the supplied ones. Only the page's layout and
styling were changed: a Week 6 theme laid out by deliverable (D2 design, D3 VTEPs, D4 MTU,
D5 evidence, D6 answers), a requirements checklist worked out from the design, a drawn overlay
diagram, and the same element ids (summary, repository, hypervisors, tenants, diagram,
commands-<hv>, evidence-<id>, answer-<key>, overlay-data).
"""
import datetime
import html
import ipaddress
import json
import os
import sys

import yaml

from build_overlay import VXLAN_OVERHEAD, all_commands, check_mtu, check_spec, load, plan

EVIDENCE = [
    ("check", "evidence6/check.txt", "check_mtu() refusing the black-hole design",
     "PROBLEM lines for every tenant, and nothing was built."),
    ("connectivity", "evidence6/connectivity.txt", "Every VM reaches its own tenant, and no other",
     "Same-tenant pings succeed; pings to another tenant's VM or network fail."),
    ("flood", "evidence6/flood.txt", "Flood and learn: the VTEP table before, the flooded broadcast, the table after",
     "Only 00:00:00:00:00:00 flood entries before; the ARP broadcast captured on a third hypervisor; learned MACs after."),
    ("isolation", "evidence6/isolation.txt", "Two tenants, one address: who answers",
     "The same IP address answers with a different MAC (a different VNI) for each tenant; the other tenant's VM captures nothing."),
    ("blackhole", "evidence6/blackhole.txt", "The black hole: tenant MTU 1500 on a 1500-byte underlay",
     "Small pings work, big pings and TCP die silently; the largest size that works and the smallest that doesn't."),
    ("fixes", "evidence6/fixes.txt", "Two fixes, measured",
     "Fix A and fix B: the don't-fragment size limits and iperf3 throughput for each."),
]

# One colour per tenant, in the order the tenants are listed.
TENANT_COLOURS = ["#0f9d8a", "#db2777", "#d97706", "#2563eb", "#65a30d", "#9333ea"]


def esc(text):
    return html.escape(str(text))


def colours(spec):
    return {t["name"]: TENANT_COLOURS[i % len(TENANT_COLOURS)] for i, t in enumerate(spec["tenants"])}


def mac_html(mac):
    """02:VV:VV:VV:00:XX with the VNI bytes highlighted."""
    b = mac.split(":")
    return f'<code class="mac">{b[0]}:<b>{":".join(b[1:4])}</b>:{":".join(b[4:])}</code>'


def chip(colour, label, small):
    return f'<span class="chip" style="--tc:{colour}">{esc(label)} <small>{esc(small)}</small></span>'


def requirements_section(spec, p):
    """The assignment's size requirements, checked against this design."""
    hvs = list(spec["hypervisors"])
    spans = {t["name"]: {hv for _, hv in t["vms"]} for t in spec["tenants"]}
    owners = {}
    for t in spec["tenants"]:
        owners.setdefault(str(ipaddress.ip_network(t["network"])), []).append(t["name"])
    overlap = [(net, names) for net, names in owners.items() if len(names) >= 2]
    span3 = [n for n, w in spans.items() if len(w) >= 3]
    shared = [hv for hv in hvs if sum(hv in w for w in spans.values()) >= 2]
    vnis = [int(t["vni"]) for t in spec["tenants"]]
    two_hv = all(len(w) >= 2 for w in spans.values())
    umtu = int(spec["underlay"]["mtu"])
    worst = max(int(t["mtu"]) for t in spec["tenants"]) + VXLAN_OVERHEAD
    present = sum(1 for e in EVIDENCE if os.path.exists(e[1]) and open(e[1]).read().strip())
    items = [
        (len(hvs) >= 3, "At least 3 hypervisors", f"{len(hvs)}: {', '.join(hvs)}"),
        (len(vnis) >= 2 and len(set(vnis)) == len(vnis), "At least 2 tenants, each with its own VNI",
         ", ".join(f"{t['name']} {t['vni']}" for t in spec["tenants"])),
        (bool(overlap), "Two tenants share the same network",
         "; ".join(f"{' and '.join(n)} on {net}" for net, n in overlap) or "none"),
        (two_hv, "Every tenant on at least 2 hypervisors",
         ", ".join(f"{n} on {len(w)}" for n, w in spans.items())),
        (bool(span3), "One tenant spans 3 hypervisors", ", ".join(span3) or "none"),
        (bool(shared), "A hypervisor hosts two tenants", ", ".join(shared) or "none"),
        (worst <= umtu, "check_mtu(): every tenant fits the underlay", f"largest packet {worst} ≤ underlay MTU {umtu}"),
        (present == len(EVIDENCE), "Evidence collected", f"{present} of {len(EVIDENCE)} files in evidence6/"),
    ]
    rows = "".join(
        f'<li class="{"ok" if ok else "no"}"><span class="tick" aria-hidden="true">{"✓" if ok else "✗"}</span>'
        f"<div><strong>{esc(label)}</strong><span>{esc(detail)}</span></div></li>"
        for ok, label, detail in items
    )
    return f'<ul class="checklist">{rows}</ul>'


def hypervisors_section(spec, p):
    col = colours(spec)
    rows = ""
    for hv, ip in p["hypervisors"].items():
        vms = [chip(col[v["tenant"]], vm, v["tenant"]) for vm, v in p["vms"].items() if v["hv"] == hv]
        rows += f"<tr><td><strong>{esc(hv)}</strong></td><td><code>{esc(ip)}</code></td><td>{''.join(vms) or '—'}</td></tr>"
    u = spec["underlay"]
    return (
        f'<p class="note">Underlay <code>{esc(u["network"])}</code>, MTU {esc(u["mtu"])}.</p>'
        f'<div class="table-wrap"><table><thead><tr><th>Hypervisor</th><th>Underlay address</th><th>VMs</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def tenants_section(spec, p):
    col = colours(spec)
    owners = {}
    for t in spec["tenants"]:
        owners.setdefault(str(ipaddress.ip_network(t["network"])), []).append(t["name"])
    parts = []
    for t in spec["tenants"]:
        net = str(ipaddress.ip_network(t["network"]))
        others = [o for o in owners[net] if o != t["name"]]
        badge = f'<span class="badge warn">Same addresses as {esc(", ".join(others))}</span>' if others else ""
        spans = len({hv for _, hv in t["vms"]})
        rows = "".join(
            f"<tr><td><strong>{esc(vm)}</strong></td><td>{esc(hv)}</td><td><code>{esc(p['vms'][vm]['ip'])}</code></td>"
            f"<td>{mac_html(p['vms'][vm]['mac'])}</td></tr>"
            for vm, hv in t["vms"]
        )
        parts.append(
            f'<article class="tenant-card" style="--tc:{col[t["name"]]}">'
            f'<header><span class="dot"></span><h3>{esc(t["name"])}: VNI {esc(t["vni"])}, <code>{esc(t["network"])}</code>, MTU {esc(t["mtu"])}</h3></header>'
            f'<div class="badges"><span class="badge">{len(t["vms"])} VMs</span><span class="badge">{spans} hypervisors</span>{badge}</div>'
            f'<div class="table-wrap"><table><thead><tr><th>VM</th><th>On</th><th>Address</th><th>MAC</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div></article>"
        )
    return "\n".join(parts)


def mtu_section(spec):
    umtu = int(spec["underlay"]["mtu"])
    rows = ""
    for t in spec["tenants"]:
        mtu = int(t["mtu"])
        wire = mtu + VXLAN_OVERHEAD
        room = umtu - wire
        state = f'<span class="pill good">fits · {room} spare</span>' if room >= 0 else f'<span class="pill bad">{-room} bytes too big</span>'
        rows += f"<tr><td><strong>{esc(t['name'])}</strong></td><td>{mtu}</td><td>+ {VXLAN_OVERHEAD}</td><td>{wire}</td><td>{umtu}</td><td>{state}</td></tr>"
    return (
        '<div class="table-wrap"><table><thead><tr><th>Tenant</th><th>Tenant MTU</th><th>VXLAN</th>'
        f"<th>On the underlay</th><th>Underlay MTU</th><th>check_mtu()</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def commands_section(spec, p, commands):
    parts = []
    for hv, cmds in commands.items():
        tenants = [t["name"] for t in spec["tenants"] if any(where == hv for _, where in t["vms"])]
        body = esc("\n".join(cmds)) if cmds else "TODO: tenant_commands() returned nothing for this hypervisor."
        parts.append(
            f'<article class="cmd-card"><header><span class="tag">VTEP</span><h3>{esc(hv)}</h3>'
            f'<code>{esc(p["hypervisors"][hv])}</code><span class="cmd-meta">{esc(", ".join(tenants))} · {len(cmds)} commands</span></header>'
            f'<pre id="commands-{esc(hv)}">{body}</pre></article>'
        )
    return "\n".join(parts)


def overlay_svg(spec, p):
    """The underlay switch, the hypervisors on it, and each hypervisor's VMs in their tenant's colour."""
    col = colours(spec)
    hvs = list(p["hypervisors"])
    slot = 240
    width = max(len(hvs) * slot, 720)
    left = (width - len(hvs) * slot) / 2
    per_hv = {hv: [vm for vm, v in p["vms"].items() if v["hv"] == hv] for hv in hvs}
    tallest = max((len(v) for v in per_hv.values()), default=0)
    height = 262 + tallest * 70 + 20
    sx = width / 2
    out = [
        f'<svg class="overlay-svg" viewBox="0 0 {width:.0f} {height}" role="img" aria-labelledby="ov-title ov-desc">',
        '<title id="ov-title">Overlay diagram</title>',
        f'<desc id="ov-desc">The underlay switch s1 joins {len(hvs)} hypervisors; each hypervisor hosts VMs coloured by tenant.</desc>',
    ]
    for i, hv in enumerate(hvs):
        cx = left + i * slot + 25 + 95
        out.append(f'<line class="u-link" x1="{sx:.0f}" y1="76" x2="{cx:.0f}" y2="130" />')
    out.append(
        f'<g class="sw"><rect x="{sx - 115:.0f}" y="18" width="230" height="58" rx="12" />'
        f'<text x="{sx:.0f}" y="44">s1 · underlay</text><text class="meta" x="{sx:.0f}" y="62">{esc(spec["underlay"]["network"])} · MTU {esc(spec["underlay"]["mtu"])}</text></g>'
    )
    for i, hv in enumerate(hvs):
        x0 = left + i * slot + 25
        vms = per_hv[hv]
        if vms:
            out.append(f'<line class="v-link" x1="{x0 + 20:.0f}" y1="194" x2="{x0 + 20:.0f}" y2="{262 + (len(vms) - 1) * 70 + 27}" />')
        out.append(
            f'<g class="hv"><rect x="{x0:.0f}" y="130" width="190" height="64" rx="12" />'
            f'<text x="{x0 + 95:.0f}" y="157">{esc(hv)}</text><text class="meta" x="{x0 + 95:.0f}" y="177">VTEP {esc(p["hypervisors"][hv])}</text></g>'
        )
        for k, vm in enumerate(vms):
            v = p["vms"][vm]
            y = 262 + k * 70
            c = col[v["tenant"]]
            out.append(
                f'<line class="v-link" x1="{x0 + 20:.0f}" y1="{y + 27}" x2="{x0 + 40:.0f}" y2="{y + 27}" />'
                f'<g class="vm"><rect x="{x0 + 40:.0f}" y="{y}" width="170" height="54" rx="10" style="stroke:{c}" />'
                f'<rect x="{x0 + 40:.0f}" y="{y}" width="8" height="54" rx="4" style="fill:{c}" />'
                f'<text class="name" x="{x0 + 58:.0f}" y="{y + 22}">{esc(vm)}</text>'
                f'<text class="meta" x="{x0 + 58:.0f}" y="{y + 41}">{esc(v["ip"])} · VNI {esc(v["vni"])}</text></g>'
            )
    out.append("</svg>")
    legend = "".join(chip(col[t["name"]], t["name"], f"VNI {t['vni']} · {t['network']}") for t in spec["tenants"])
    return "\n".join(out) + f'<div class="legend">{legend}</div>'


def evidence_section(ev_id, path, title, look_for):
    if os.path.exists(path) and open(path).read().strip():
        body = f'<pre id="evidence-{ev_id}">{esc(open(path).read().rstrip())}</pre>'
    else:
        print(f"WARNING: {path} is missing or empty")
        body = f'<pre id="evidence-{ev_id}" class="missing">Missing: {esc(path)}</pre>'
    return (
        f'<details class="evidence-card" id="evidence-card-{ev_id}"><summary><span class="ev-title">{esc(title)}</span>'
        f'<span class="ev-look">{esc(look_for)}</span><span class="file">{esc(path)}</span></summary>{body}</details>'
    )


def answers_section(page):
    parts = []
    for key, qa in page.get("answers", {}).items():
        answer = str(qa.get("answer") or "").strip()
        if not answer:
            print(f"WARNING: page6.yaml has no answer for '{key}'")
            answer = "(Not answered yet.)"
        paragraphs = "".join(f"<p>{esc(p.strip())}</p>" for p in answer.split("\n\n") if p.strip())
        parts.append(
            f'<section class="answer-card" id="answer-{esc(key)}"><span class="answer-key">{esc(key.replace("_", " "))}</span>'
            f'<h3>{esc(qa.get("question", key))}</h3>{paragraphs}</section>'
        )
    return "\n".join(parts)


CSS = """
  :root { color-scheme:light; --bg:#f6f4ef; --paper:#fff; --ink:#1d1b33; --muted:#6a6780; --line:#e6e2d8; --indigo:#4338ca; --indigo-dark:#312e81; --night:#1e1b4b; --amber:#f59e0b; --amber-soft:#fef3c7; --good:#047857; --bad:#b91c1c; }
  * { box-sizing:border-box; } html { scroll-behavior:smooth; scroll-padding-top:4.5rem; }
  body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 "Segoe UI",system-ui,-apple-system,sans-serif; }
  a { color:var(--indigo); } a:focus-visible, summary:focus-visible { outline:3px solid var(--amber); outline-offset:3px; border-radius:4px; }
  .skip-link { position:absolute; left:-9999px; top:1rem; z-index:20; background:#fff; padding:.7rem 1rem; } .skip-link:focus { left:1rem; }
  .topbar { position:sticky; top:0; z-index:10; display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.65rem max(1rem,calc((100% - 1120px)/2)); background:#f6f4efeb; border-bottom:1px solid var(--line); backdrop-filter:blur(12px); }
  .brand { display:flex; align-items:center; gap:.55rem; color:var(--ink); font-weight:800; white-space:nowrap; } .brand-mark { display:inline-grid; place-items:center; width:2rem; height:2rem; border-radius:8px; background:var(--night); color:var(--amber); font-size:.78rem; }
  .nav { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:.2rem; } .nav a { color:var(--muted); padding:.4rem .6rem; font-size:.86rem; font-weight:600; text-decoration:none; border-radius:8px; } .nav a:hover { color:var(--indigo-dark); background:#4338ca12; } .nav b { color:var(--amber); font-weight:800; margin-right:.2rem; }
  main { max-width:1120px; margin:auto; padding:1.75rem 1rem 4rem; }
  .hero { position:relative; overflow:hidden; display:grid; grid-template-columns:minmax(0,1.45fr) minmax(260px,.75fr); gap:2rem; padding:clamp(1.75rem,5vw,3.75rem); border-radius:22px; color:#eef0ff;
    background:linear-gradient(#ffffff0b 1px,transparent 1px) 0 0/30px 30px, linear-gradient(90deg,#ffffff0b 1px,transparent 1px) 0 0/30px 30px, linear-gradient(135deg,#1e1b4b 0%,#312e81 55%,#5b21b6 100%); }
  .hero:before { content:""; position:absolute; right:-80px; top:-80px; width:280px; height:280px; border-radius:50%; background:radial-gradient(circle,#f59e0b55,transparent 70%); pointer-events:none; }
  .eyebrow { margin:0 0 .7rem; color:var(--amber); font-size:.74rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
  h1 { margin:0 0 1rem; font-size:clamp(2.2rem,5.5vw,4rem); line-height:1.04; letter-spacing:-.04em; } .hero-copy>p:not(.eyebrow) { max-width:640px; color:#c7c9f3; font-size:1.05rem; } .hero code { color:var(--amber); font-weight:700; }
  .hero-actions { display:flex; flex-wrap:wrap; gap:.7rem; margin-top:1.4rem; } .button { display:inline-flex; align-items:center; gap:.5rem; padding:.68rem 1rem; border-radius:10px; font-weight:750; text-decoration:none; } .button-primary { background:var(--amber); color:var(--night); } .button-ghost { border:1px solid #ffffff55; color:#eef0ff; }
  .hero-aside { position:relative; z-index:1; align-self:end; display:grid; gap:.7rem; padding:1.1rem; border:1px solid #ffffff2a; border-radius:14px; background:#ffffff10; } .kv span { display:block; color:#a5a8e6; font-size:.72rem; letter-spacing:.1em; text-transform:uppercase; } .kv strong { color:#fff; font:700 1.25rem/1.25 ui-monospace,Consolas,monospace; } .kv.big strong { font-size:clamp(1.4rem,3vw,1.75rem); }
  .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:.8rem; margin:1rem 0 2.75rem; } .stat { padding:.95rem 1.1rem; border:1px solid var(--line); border-left:4px solid var(--indigo); border-radius:12px; background:var(--paper); } .stat:nth-child(2) { border-left-color:#db2777; } .stat:nth-child(3) { border-left-color:#0f9d8a; } .stat:nth-child(4) { border-left-color:var(--amber); } .stat strong { display:block; font-size:1.6rem; line-height:1.15; } .stat span { color:var(--muted); font-size:.84rem; }
  .page-section { margin:2.75rem 0; scroll-margin-top:4.5rem; }
  .section-heading { display:flex; align-items:flex-start; gap:1rem; margin-bottom:1.1rem; } .step { flex:none; display:grid; place-items:center; width:3rem; height:3rem; border-radius:12px; background:var(--night); color:var(--amber); font:800 1rem ui-monospace,Consolas,monospace; } .section-heading h2 { margin:0; font-size:clamp(1.55rem,3.5vw,2.1rem); letter-spacing:-.03em; line-height:1.2; } .section-heading p { margin:.25rem 0 0; color:var(--muted); }
  .hero>*,.stats>*,.grid>*,.tenants>*,.cmd-grid>*,.evidence-list>*,.answer-grid>* { min-width:0; } main { overflow-wrap:break-word; }
  .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; align-items:start; } .wide { grid-column:1/-1; }
  .panel,.tenant-card,.cmd-card,.answer-card,.evidence-card { border:1px solid var(--line); border-radius:14px; background:var(--paper); }
  .panel { padding:1.1rem; } .panel h3 { margin:0 0 .7rem; font-size:1rem; } .note { margin:0 0 .5rem; color:var(--muted); font-size:.9rem; }
  .checklist { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.6rem; margin:0; padding:0; list-style:none; } .checklist li { display:flex; gap:.75rem; align-items:flex-start; padding:.8rem .9rem; border:1px solid var(--line); border-radius:12px; background:var(--paper); } .checklist strong { display:block; font-size:.93rem; } .checklist span:not(.tick) { color:var(--muted); font-size:.84rem; } .tick { flex:none; display:grid; place-items:center; width:1.6rem; height:1.6rem; border-radius:50%; font-weight:800; } .ok .tick { background:#d1fae5; color:var(--good); } .no .tick { background:#fee2e2; color:var(--bad); }
  .diagram-panel { overflow-x:auto; background:linear-gradient(#4338ca08 1px,transparent 1px) 0 0/24px 24px, linear-gradient(90deg,#4338ca08 1px,transparent 1px) 0 0/24px 24px, #fbfaff; }
  .overlay-svg { display:block; width:100%; min-width:680px; height:auto; }
  .overlay-svg .u-link { stroke:var(--indigo); stroke-width:3; } .overlay-svg .v-link { stroke:#a5a3c9; stroke-width:2; }
  .overlay-svg .sw rect { fill:var(--night); } .overlay-svg .sw text { fill:#fff; text-anchor:middle; font:800 16px "Segoe UI",system-ui,sans-serif; } .overlay-svg .sw .meta { fill:var(--amber); font:600 11px ui-monospace,Consolas,monospace; }
  .overlay-svg .hv rect { fill:#eef0ff; stroke:var(--indigo); stroke-width:2.5; } .overlay-svg .hv text { fill:var(--indigo-dark); text-anchor:middle; font:800 17px "Segoe UI",system-ui,sans-serif; } .overlay-svg .hv .meta { fill:#5b5a85; font:11px ui-monospace,Consolas,monospace; }
  .overlay-svg .vm rect { fill:#fff; stroke-width:2; } .overlay-svg .vm .name { fill:var(--ink); font:800 14px "Segoe UI",system-ui,sans-serif; } .overlay-svg .vm .meta { fill:#5d5b74; font:11px ui-monospace,Consolas,monospace; }
  .legend { display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.8rem; }
  .chip { display:inline-flex; align-items:center; gap:.35rem; margin:.1rem .3rem .1rem 0; padding:.18rem .55rem .18rem .45rem; border-radius:999px; border:1px solid color-mix(in srgb,var(--tc) 35%,#fff); background:color-mix(in srgb,var(--tc) 9%,#fff); color:var(--ink); font-size:.82rem; font-weight:700; white-space:nowrap; } .chip:before { content:""; width:.55rem; height:.55rem; border-radius:50%; background:var(--tc); } .chip small { color:var(--muted); font-weight:500; }
  .tenants { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr)); gap:1rem; margin-top:1rem; }
  .tenant-card { overflow:hidden; border-top:5px solid var(--tc); } .tenant-card header { display:flex; align-items:center; gap:.6rem; padding:1rem 1rem .4rem; } .tenant-card h3 { margin:0; font-size:1rem; } .dot { flex:none; width:.8rem; height:.8rem; border-radius:50%; background:var(--tc); }
  .badges { display:flex; flex-wrap:wrap; gap:.4rem; padding:0 1rem .5rem; } .badge { padding:.16rem .5rem; border-radius:999px; background:#f1effa; color:#4c4a7a; font-size:.74rem; font-weight:700; } .badge.warn { background:var(--amber-soft); color:#92400e; }
  .tenant-card .table-wrap { padding:0 .75rem .6rem; } .tenant-card table { font-size:.84rem; } .tenant-card th,.tenant-card td { padding:.55rem .4rem; } .tenant-card td code { white-space:nowrap; overflow-wrap:normal; }
  .table-wrap { overflow-x:auto; } table { width:100%; border-collapse:collapse; font-size:.9rem; } th,td { padding:.6rem .55rem; border-bottom:1px solid #efece4; text-align:left; vertical-align:top; } th { color:var(--muted); font-size:.71rem; letter-spacing:.08em; text-transform:uppercase; } tbody tr:last-child td { border-bottom:0; }
  code { color:var(--indigo-dark); font:600 .9em ui-monospace,SFMono-Regular,Consolas,monospace; overflow-wrap:anywhere; } .mac { color:var(--muted); font-weight:500; } .mac b { color:#db2777; }
  .pill { display:inline-block; white-space:nowrap; padding:.2rem .45rem; border-radius:6px; font-size:.78rem; font-weight:700; } .pill.good { background:#d1fae5; color:var(--good); } .pill.bad { background:#fee2e2; color:var(--bad); }
  .callout { display:flex; gap:.8rem; align-items:flex-start; margin-top:1rem; padding:.95rem 1.1rem; border:1px solid #fde68a; border-radius:12px; background:#fffbeb; color:#78350f; } .callout strong { display:block; } .callout p { margin:.15rem 0 0; font-size:.9rem; }
  .cmd-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; } .cmd-card { overflow:hidden; } .cmd-card header { display:flex; flex-wrap:wrap; align-items:center; gap:.55rem; padding:.85rem 1rem .7rem; } .cmd-card h3 { margin:0; font-size:1.1rem; } .cmd-meta { margin-left:auto; color:var(--muted); font-size:.78rem; }
  .tag { padding:.2rem .4rem; border-radius:6px; background:var(--night); color:var(--amber); font-size:.62rem; font-weight:800; letter-spacing:.1em; }
  pre { max-height:440px; overflow:auto; margin:0; padding:1rem 1.1rem; background:var(--night); color:#e0e2ff; font:.78rem/1.55 ui-monospace,SFMono-Regular,Consolas,monospace; white-space:pre-wrap; overflow-wrap:anywhere; } pre.missing { background:#fef2f2; color:var(--bad); }
  .evidence-list { display:grid; gap:.7rem; } .evidence-card { overflow:hidden; } .evidence-card summary { position:relative; display:grid; gap:.15rem; padding:.95rem 2.8rem .95rem 1.1rem; cursor:pointer; list-style:none; } .evidence-card summary::-webkit-details-marker { display:none; } .evidence-card summary:after { content:"+"; position:absolute; right:1rem; top:.85rem; display:grid; place-items:center; width:1.6rem; height:1.6rem; border-radius:50%; background:#eef0ff; color:var(--indigo); font-weight:800; } .evidence-card[open] summary:after { content:"−"; background:var(--amber); color:var(--night); } .ev-title { font-weight:750; } .ev-look { color:var(--muted); font-size:.86rem; } .file { color:var(--indigo); font:.74rem ui-monospace,monospace; }
  .answer-grid { display:grid; gap:.8rem; } .answer-card { padding:1.1rem 1.25rem; border-left:4px solid var(--indigo); } .answer-key { color:#b45309; font-size:.72rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; } .answer-card h3 { margin:.3rem 0 .6rem; font-size:1.05rem; line-height:1.4; } .answer-card p { margin:.55rem 0 0; color:#3f3d56; }
  footer { display:flex; flex-wrap:wrap; justify-content:space-between; gap:.75rem; margin-top:3.5rem; padding:1.1rem 0; border-top:1px solid var(--line); color:var(--muted); font-size:.84rem; } footer a { font-weight:700; text-decoration:none; }
  @media(max-width:850px) { .grid,.cmd-grid,.checklist { grid-template-columns:1fr; } .hero { grid-template-columns:1fr; } .hero-aside { max-width:460px; } }
  @media(max-width:620px) { .topbar { flex-direction:column; align-items:flex-start; gap:.3rem; } .nav { justify-content:flex-start; width:100%; overflow-x:auto; flex-wrap:nowrap; } .nav a { white-space:nowrap; } .hero { padding:1.5rem 1.25rem; border-radius:16px; } .stats { grid-template-columns:1fr 1fr; } .step { width:2.5rem; height:2.5rem; font-size:.85rem; } }
  @media(prefers-reduced-motion:reduce) { html { scroll-behavior:auto; } }
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#1e1b4b">
<meta name="description" content="Week 6 VXLAN overlay: a multi-tenant data centre built from data, with flood-and-learn, isolation and MTU evidence.">
<title>Week 6 — Virtualisation, Overlays and Software Forwarding · Overlay {last4}</title>
<style>{css}</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="topbar">
  <span class="brand"><span class="brand-mark">W6</span>Week 6 · Overlay {last4}</span>
  <nav class="nav" aria-label="Page sections">
    <a href="#requirements"><b>✓</b>Requirements</a><a href="#design"><b>D2</b>Design</a><a href="#vteps"><b>D3</b>VTEPs</a><a href="#mtu"><b>D4</b>MTU</a><a href="#evidence"><b>D5</b>Evidence</a><a href="#reflection"><b>D6</b>Answers</a>
  </nav>
</header>
<main id="main">
  <section class="hero" id="overview">
    <div class="hero-copy">
      <p class="eyebrow">Week 6 · Virtualisation, Overlays and Software Forwarding · Assignment: overlay your own data centre</p>
      <h1>My data centre overlay, from data</h1>
      <p id="summary">{n_hv} hypervisors and {n_tenants} tenants ({n_vms} VMs) on <code>{v4_block}</code>, joined by VXLAN.
Every tenant's MTU was checked against the underlay before anything was built.</p>
      <div class="hero-actions">
        <a class="button button-primary" href="#design">See the design <span aria-hidden="true">↓</span></a>
        <a class="button button-ghost" id="repository" href="{repo}">Repository <span aria-hidden="true">↗</span></a>
      </div>
    </div>
    <aside class="hero-aside" aria-label="Addresses">
      <div class="kv big"><span>IPv4 block</span><strong>{v4_block}</strong></div>
      <div class="kv"><span>Underlay</span><strong>{underlay}</strong></div>
      <div class="kv"><span>Student ID ending · generated</span><strong>{last4} · {today}</strong></div>
    </aside>
  </section>

  <section class="stats" aria-label="Overlay summary">
    <div class="stat"><strong>{n_hv}</strong><span>Hypervisors (VTEPs)</span></div>
    <div class="stat"><strong>{n_tenants}</strong><span>Tenants, one VNI each</span></div>
    <div class="stat"><strong>{n_vms}</strong><span>VMs</span></div>
    <div class="stat"><strong>{umtu}</strong><span>Underlay MTU</span></div>
  </section>

  <section class="page-section" id="requirements">
    <div class="section-heading"><span class="step">✓</span><div><h2>Assignment requirements</h2><p>Checked against <code>{source}</code> when this page was generated.</p></div></div>
    {requirements}
  </section>

  <section class="page-section" id="design">
    <div class="section-heading"><span class="step">D2</span><div><h2>The design: hypervisors and tenants</h2><p>Every address, MAC and VTEP below is worked out from the YAML file.</p></div></div>
    <div class="grid">
      <article class="panel diagram-panel wide"><h3>Diagram</h3><div id="diagram">{diagram}</div></article>
      <article class="panel wide"><h3>Hypervisors and the underlay</h3><section id="hypervisors">{hypervisors}</section></article>
    </div>
    <section class="tenants" id="tenants">{tenants}</section>
    <aside class="callout"><span aria-hidden="true">◆</span><div><strong>Reading a MAC address</strong><p>Each VM's MAC is <code>02:VV:VV:VV:00:XX</code>. The highlighted middle three bytes are the tenant's VNI, and the last byte is the VM's address. Two VMs can share an IP address but never a MAC.</p></div></aside>
  </section>

  <section class="page-section" id="vteps">
    <div class="section-heading"><span class="step">D3</span><div><h2>VTEP commands, as built</h2><p>What <code>tenant_commands()</code> ran on each hypervisor: bridge, VXLAN device, VM ports, flood list ({n_cmds} commands in all).</p></div></div>
    <section class="cmd-grid" id="commands">{commands}</section>
  </section>

  <section class="page-section" id="mtu">
    <div class="section-heading"><span class="step">D4</span><div><h2>MTU plan</h2><p>Each tenant's largest packet plus {overhead} bytes of VXLAN must fit the underlay; <code>check_mtu()</code> refuses the design otherwise.</p></div></div>
    <article class="panel">{mtu_plan}</article>
  </section>

  <section class="page-section" id="evidence">
    <div class="section-heading"><span class="step">D5</span><div><h2>Evidence from the running overlay</h2><p>Captured in Mininet. Open an item to read the output.</p></div></div>
    <div class="evidence-list">{evidence}</div>
  </section>

  <section class="page-section" id="reflection">
    <div class="section-heading"><span class="step">D6</span><div><h2>What I learned</h2><p>Design, isolation, flood and learn, MTU fixes and the P4 alternative.</p></div></div>
    <section class="answer-grid" id="answers">{answers}</section>
  </section>

  <footer><span>Generated from <code>{source}</code> by <code>make_page6.py</code> on {today}</span><a href="{repo}">Source repository ↗</a></footer>
</main>

<script type="application/json" id="overlay-data">{data}</script>
</body>
</html>
"""


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 make_page6.py <overlay.yaml>")
    source = sys.argv[1]
    spec = load(source)
    problems = check_spec(spec)
    if not problems:
        problems = check_mtu(spec)
    if problems:
        for pr in problems:
            print("PROBLEM:", pr)
        sys.exit("Fix the design first: a design with problems doesn't get published.")

    commands = all_commands(spec)
    if not any(commands.values()):
        print("WARNING: tenant_commands() returned no commands: the page will say TODO.")
    with open("page6.yaml") as f:
        page = yaml.safe_load(f)
    p = plan(spec)
    last4 = str(spec["student_id_last4"])
    os.makedirs("docs/week6", exist_ok=True)
    with open("docs/week6/index.html", "w", encoding="utf-8") as f:
        f.write(
            PAGE.format(
                css=CSS,
                last4=esc(last4),
                source=esc(source),
                today=datetime.date.today().isoformat(),
                n_hv=len(spec["hypervisors"]),
                n_tenants=len(spec["tenants"]),
                n_vms=len(p["vms"]),
                n_cmds=sum(len(c) for c in commands.values()),
                umtu=esc(spec["underlay"]["mtu"]),
                underlay=esc(spec["underlay"]["network"]),
                overhead=VXLAN_OVERHEAD,
                v4_block=f"10.{int(last4[2:])}.0.0/16",
                repo=esc(page.get("repository", "")),
                requirements=requirements_section(spec, p),
                hypervisors=hypervisors_section(spec, p),
                tenants=tenants_section(spec, p),
                mtu_plan=mtu_section(spec),
                diagram=overlay_svg(spec, p),
                commands=commands_section(spec, p, commands),
                evidence="\n".join(evidence_section(*e) for e in EVIDENCE),
                answers=answers_section(page),
                data=json.dumps({"design": spec, "commands": commands}, indent=2).replace("</", "<\\/"),
            )
        )
    print("Wrote docs/week6/index.html")


if __name__ == "__main__":
    main()
