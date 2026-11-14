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
styling were changed, to match the Week 3 page: a drawn overlay diagram, tenant cards, an MTU
plan, collapsible evidence and the same element ids (summary, hypervisors, tenants, diagram,
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
    ("check", "evidence6/check.txt", "check_mtu() refusing the black-hole design"),
    ("connectivity", "evidence6/connectivity.txt", "Every VM reaches its own tenant, and no other"),
    ("flood", "evidence6/flood.txt", "Flood and learn: the VTEP table before, the flooded broadcast, the table after"),
    ("isolation", "evidence6/isolation.txt", "Two tenants, one address: who answers"),
    ("blackhole", "evidence6/blackhole.txt", "The black hole: tenant MTU 1500 on a 1500-byte underlay"),
    ("fixes", "evidence6/fixes.txt", "Two fixes, measured"),
]

# One colour per tenant, in the order the tenants are listed.
TENANT_COLOURS = ["#0d8a8c", "#5b5fc7", "#c07a0c", "#c2416b", "#3d8b3d", "#7a4fb5"]


def esc(text):
    return html.escape(str(text))


def colours(spec):
    return {t["name"]: TENANT_COLOURS[i % len(TENANT_COLOURS)] for i, t in enumerate(spec["tenants"])}


def mac_html(mac):
    """02:VV:VV:VV:00:XX with the VNI bytes highlighted."""
    b = mac.split(":")
    return f'<code class="mac">{b[0]}:<b>{":".join(b[1:4])}</b>:{":".join(b[4:])}</code>'


def hypervisors_section(spec, p):
    col = colours(spec)
    rows = ""
    for hv, ip in p["hypervisors"].items():
        vms = [
            f'<span class="chip" style="--tc:{col[v["tenant"]]}">{esc(vm)} <small>{esc(v["tenant"])}</small></span>'
            for vm, v in p["vms"].items() if v["hv"] == hv
        ]
        rows += f"<tr><td><strong>{esc(hv)}</strong></td><td><code>{esc(ip)}</code></td><td>{''.join(vms) or '—'}</td></tr>"
    u = spec["underlay"]
    return (
        f'<p class="panel-note">Underlay <code>{esc(u["network"])}</code>, MTU {esc(u["mtu"])}.</p>'
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
        badge = f'<span class="badge overlap">Same addresses as {esc(", ".join(others))}</span>' if others else ""
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
        state = f'<span class="hop ok">fits · {room} spare</span>' if room >= 0 else f'<span class="hop bad">{-room} bytes too big</span>'
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
            f'<article class="cmd-card"><header><span class="router-mark">VTEP</span><h3>{esc(hv)}</h3>'
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
        x0 = left + i * slot + 25
        cx = x0 + 95
        out.append(f'<line class="u-link" x1="{sx:.0f}" y1="76" x2="{cx:.0f}" y2="130" />')
    out.append(
        f'<g class="sw"><rect x="{sx - 110:.0f}" y="18" width="220" height="58" rx="12" />'
        f'<text x="{sx:.0f}" y="44">s1</text><text class="meta" x="{sx:.0f}" y="62">underlay {esc(spec["underlay"]["network"])} · MTU {esc(spec["underlay"]["mtu"])}</text></g>'
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
    legend = "".join(
        f'<span class="chip" style="--tc:{col[t["name"]]}">{esc(t["name"])} <small>VNI {esc(t["vni"])} · {esc(t["network"])}</small></span>'
        for t in spec["tenants"]
    )
    return "\n".join(out) + f'<div class="legend">{legend}</div>'


def evidence_section(ev_id, path, title):
    if os.path.exists(path) and open(path).read().strip():
        body = f'<pre id="evidence-{ev_id}">{esc(open(path).read().rstrip())}</pre>'
    else:
        print(f"WARNING: {path} is missing or empty")
        body = f'<pre id="evidence-{ev_id}" class="missing">Missing: {esc(path)}</pre>'
    return (
        f'<details class="evidence-card" id="evidence-card-{ev_id}"><summary><span class="evidence-title">{esc(title)}</span>'
        f'<span class="file">{esc(path)}</span></summary>{body}</details>'
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
  :root { color-scheme:light; --ink:#142b33; --muted:#5d727b; --teal:#087e83; --teal-dark:#075c64; --lime:#c6f36a; --paper:#fff; --line:#d5e2dc; --navy:#102a35; --shadow:0 18px 48px #163c3b12; }
  * { box-sizing:border-box; } html { scroll-behavior:smooth; scroll-padding-top:5.5rem; }
  body { margin:0; background:radial-gradient(ellipse at 12% 18%,#d4e9e1 0,transparent 38%),linear-gradient(180deg,#e4efea 0,#f3f6f2 36rem,#eef3f0 100%); color:var(--ink); font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }
  a { color:var(--teal-dark); } a:focus-visible, summary:focus-visible { outline:3px solid #dc8d27; outline-offset:3px; border-radius:4px; }
  .skip-link { position:absolute; left:-9999px; top:1rem; z-index:20; background:#fff; padding:.7rem 1rem; } .skip-link:focus { left:1rem; }
  .topbar { position:sticky; top:0; z-index:10; display:flex; align-items:center; justify-content:space-between; gap:1.5rem; padding:.75rem max(1.25rem,calc((100% - 1160px)/2)); background:#102a35f5; color:#eff8f3; backdrop-filter:blur(14px); }
  .brand { color:#eff8f3; text-decoration:none; font-weight:750; letter-spacing:.02em; white-space:nowrap; } .brand-mark { display:inline-grid; place-items:center; width:2rem; height:2rem; margin-right:.55rem; border-radius:9px; background:var(--lime); color:var(--navy); font-size:.78rem; }
  .nav { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:.25rem; } .nav a { color:#c4d9d4; padding:.45rem .65rem; font-size:.88rem; text-decoration:none; border-radius:8px; } .nav a:hover { color:#fff; background:#ffffff18; } .nav .sep { width:1px; margin:.35rem .35rem; background:#ffffff30; }
  main { max-width:1160px; margin:auto; padding:2rem 1.25rem 4rem; }
  .hero { position:relative; overflow:hidden; display:grid; grid-template-columns:minmax(0,1.5fr) minmax(250px,.7fr); gap:2rem; padding:clamp(2rem,5vw,4.25rem); border-radius:26px; color:#f2faf5; background:radial-gradient(circle at 91% 10%,#247e78 0,transparent 34%),linear-gradient(125deg,#102a35 5%,#15444b 70%,#0e625f); box-shadow:var(--shadow); }
  .hero:after { content:""; position:absolute; width:330px; height:330px; right:-140px; bottom:-220px; border:1px solid #ffffff24; border-radius:50%; box-shadow:0 0 0 35px #ffffff09,0 0 0 70px #ffffff06; pointer-events:none; }
  .eyebrow,.section-kicker { margin:0 0 .6rem; color:var(--teal); font-size:.75rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; } .hero .eyebrow { color:var(--lime); }
  h1 { max-width:700px; margin:.1rem 0 1rem; font-size:clamp(2.4rem,6vw,4.4rem); line-height:1.02; letter-spacing:-.05em; } .hero-copy>p:not(.eyebrow) { max-width:650px; color:#d3e5df; font-size:1.06rem; } .hero code { color:var(--lime); }
  .hero-actions { display:flex; flex-wrap:wrap; gap:.7rem; margin-top:1.5rem; } .button { display:inline-flex; align-items:center; gap:.55rem; padding:.7rem 1rem; border-radius:10px; font-weight:750; text-decoration:none; } .button-primary { background:var(--lime); color:var(--navy); } .button-ghost { border:1px solid #ffffff50; color:#f2faf5; }
  .hero-aside { align-self:end; position:relative; z-index:1; padding:1.15rem; border:1px solid #ffffff28; border-radius:16px; background:#ffffff0c; backdrop-filter:blur(8px); } .aside-label { color:#a9c6bd; font-size:.76rem; text-transform:uppercase; letter-spacing:.1em; } .block-value { display:block; margin:.2rem 0 .8rem; color:#fff; font:700 clamp(1.35rem,3vw,1.8rem)/1.2 ui-monospace,monospace; } .hero-meta { display:flex; justify-content:space-between; gap:1rem; padding-top:.75rem; border-top:1px solid #ffffff25; color:#c6d9d3; font-size:.82rem; }
  .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:.85rem; margin:1.1rem 0 3.5rem; } .stat { padding:1rem 1.15rem; border:1px solid #d3e1da; border-radius:14px; background:#d9ece4; box-shadow:0 8px 25px #163c3b08; } .stat:nth-child(2) { background:#dcecf0; } .stat:nth-child(3) { background:#e8e5f2; } .stat:nth-child(4) { background:#f4ead4; } .stat strong { display:block; color:var(--teal-dark); font-size:1.65rem; line-height:1.15; } .stat span { color:#4f6870; font-size:.84rem; }
  .page-section { margin:3.2rem 0; padding:clamp(1.25rem,3vw,2rem); border:1px solid #d3e1da; border-radius:22px; background:linear-gradient(145deg,#ffffff,#eaf5ef); box-shadow:var(--shadow); scroll-margin-top:5rem; }
  #vteps { background:linear-gradient(145deg,#e5ebf8,#f4f5fb); border-color:#d6deef; } #evidence { background:linear-gradient(145deg,#dcefeb,#f0f8f5); border-color:#cfe2dc; } #reflection { background:linear-gradient(145deg,#f3ead9,#fcf8ed); border-color:#eadfc8; }
  .section-heading { display:flex; align-items:end; justify-content:space-between; gap:1rem; margin-bottom:1.2rem; padding-bottom:1rem; border-bottom:1px solid #ccded5; } .section-heading h2 { margin:0; font-size:clamp(1.8rem,4vw,2.45rem); letter-spacing:-.04em; } .section-heading p:not(.section-kicker) { margin:.35rem 0 0; color:var(--muted); }
  .section-kicker { display:inline-block; padding:.22rem .5rem; border-radius:999px; background:#dcefe5; } #vteps .section-kicker { background:#e0e5f3; color:#4b5b91; } #evidence .section-kicker { background:#d2eae3; } #reflection .section-kicker { background:#efe1c4; color:#806322; }
  .section-index { flex:none; padding:.35rem .6rem; border:1px solid #d1e0d8; border-radius:8px; background:#f8fcf9; color:#53756b; font:700 .78rem ui-monospace,monospace; }
  .hero>*,.stats>*,.grid>*,.tenants>*,.cmd-grid>*,.evidence-list>*,.answer-grid>* { min-width:0; } main { overflow-wrap:break-word; }
  .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; align-items:start; } .wide { grid-column:1/-1; }
  .panel,.tenant-card,.cmd-card,.answer-card,.evidence-card { border:1px solid var(--line); border-radius:17px; background:var(--paper); box-shadow:0 10px 30px #163c3b08; }
  .panel { padding:1.15rem; } .panel h3 { margin:.2rem 0 .7rem; font-size:1rem; } .panel-note { margin:0 0 .5rem; color:var(--muted); font-size:.9rem; }
  .diagram-panel { overflow-x:auto; background:linear-gradient(145deg,#e6f3ee,#f7faf5); }
  .overlay-svg { display:block; width:100%; min-width:680px; height:auto; }
  .overlay-svg .u-link { stroke:#2c7773; stroke-width:3; } .overlay-svg .v-link { stroke:#8aa9a0; stroke-width:2; }
  .overlay-svg .sw rect { fill:#102a35; } .overlay-svg .sw text { fill:#eff8f3; text-anchor:middle; font:800 17px system-ui,sans-serif; } .overlay-svg .sw .meta { fill:#a9c6bd; font:11px ui-monospace,Consolas,monospace; }
  .overlay-svg .hv rect { fill:#e0f0e9; stroke:#28766e; stroke-width:2.5; } .overlay-svg .hv text { fill:#174e4a; text-anchor:middle; font:800 17px system-ui,sans-serif; } .overlay-svg .hv .meta { fill:#567a72; font:11px ui-monospace,Consolas,monospace; }
  .overlay-svg .vm rect { fill:#fff; stroke-width:2; } .overlay-svg .vm .name { fill:#163c3b; font:800 14px system-ui,sans-serif; } .overlay-svg .vm .meta { fill:#536d69; font:11px ui-monospace,Consolas,monospace; }
  .legend { display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.8rem; }
  .chip { display:inline-flex; align-items:center; gap:.35rem; margin:.1rem .3rem .1rem 0; padding:.2rem .55rem .2rem .45rem; border-radius:999px; border:1px solid color-mix(in srgb,var(--tc) 35%,#fff); background:color-mix(in srgb,var(--tc) 10%,#fff); color:#1d3a40; font-size:.82rem; font-weight:700; white-space:nowrap; }
  .chip:before { content:""; width:.55rem; height:.55rem; border-radius:50%; background:var(--tc); } .chip small { color:var(--muted); font-weight:500; }
  .tenants { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr)); gap:1rem; margin-top:1rem; }
  .tenant-card { overflow:hidden; border-top:5px solid var(--tc); } .tenant-card header { display:flex; align-items:center; gap:.6rem; padding:1rem 1rem .4rem; } .tenant-card h3 { margin:0; font-size:1.02rem; } .dot { flex:none; width:.8rem; height:.8rem; border-radius:50%; background:var(--tc); }
  .badges { display:flex; flex-wrap:wrap; gap:.4rem; padding:0 1rem .5rem; } .badge { padding:.18rem .5rem; border-radius:999px; background:#eef4f1; color:#456860; font-size:.74rem; font-weight:700; } .badge.overlap { background:#fdf0dc; color:#8a5a12; }
  .tenant-card .table-wrap { padding:0 .75rem .6rem; } .tenant-card table { font-size:.84rem; } .tenant-card th,.tenant-card td { padding:.55rem .4rem; } .tenant-card td code { white-space:nowrap; overflow-wrap:normal; }
  .table-wrap { overflow-x:auto; } table { width:100%; border-collapse:collapse; font-size:.9rem; } th,td { padding:.62rem .55rem; border-bottom:1px solid #eaf0ed; text-align:left; vertical-align:top; } th { color:var(--muted); font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; } tbody tr:last-child td { border-bottom:0; }
  code { color:#135c60; font:600 .9em ui-monospace,SFMono-Regular,Consolas,monospace; overflow-wrap:anywhere; } .mac { color:#5d727b; font-weight:500; } .mac b { color:#135c60; }
  .hop { display:inline-block; white-space:nowrap; padding:.22rem .45rem; border-radius:6px; font-size:.78rem; font-weight:700; } .ok { background:#e3f2e8; color:#2c6a45; } .bad { background:#fde8e4; color:#9b3420; }
  .callout { display:flex; gap:.9rem; align-items:flex-start; margin-top:1rem; padding:1rem 1.1rem; border:1px solid #e9dfc5; border-radius:13px; background:#fbf7ec; color:#5b4d2b; } .callout strong { display:block; color:#624d1d; } .callout p { margin:.15rem 0 0; font-size:.9rem; }
  .cmd-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; } .cmd-card { overflow:hidden; } .cmd-card header { display:flex; flex-wrap:wrap; align-items:center; gap:.55rem; padding:.9rem 1rem .7rem; } .cmd-card h3 { margin:0; font-size:1.15rem; } .cmd-meta { margin-left:auto; color:var(--muted); font-size:.78rem; }
  .router-mark { padding:.22rem .4rem; border-radius:6px; background:#e0e5f3; color:#4b5b91; font-size:.62rem; font-weight:800; letter-spacing:.1em; }
  pre { max-height:420px; overflow:auto; margin:0; padding:1rem 1.1rem; border-top:1px solid #e6eeea; background:#102a35; color:#dcece5; font:.78rem/1.55 ui-monospace,SFMono-Regular,Consolas,monospace; white-space:pre-wrap; overflow-wrap:anywhere; } pre.missing { background:#fff1ec; color:#8b4027; }
  .evidence-list { display:grid; gap:.8rem; } .evidence-card { overflow:hidden; } .evidence-card summary { position:relative; display:flex; flex-direction:column; gap:.15rem; padding:1rem 2.6rem 1rem 1.1rem; cursor:pointer; list-style:none; } .evidence-card summary::-webkit-details-marker { display:none; } .evidence-card summary:after { content:"+"; position:absolute; right:1.1rem; top:1rem; color:var(--teal); font-size:1.15rem; font-weight:700; } .evidence-card[open] summary:after { content:"−"; } .evidence-title { color:var(--ink); font-weight:750; } .file { color:var(--muted); font:.75rem ui-monospace,monospace; }
  .answer-grid { display:grid; gap:.8rem; } .answer-card { padding:1.15rem 1.3rem; } .answer-key { color:var(--teal); font-size:.72rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; } .answer-card h3 { margin:.35rem 0 .65rem; font-size:1.08rem; line-height:1.4; } .answer-card p { margin:.55rem 0 0; color:#425960; }
  footer { display:flex; flex-wrap:wrap; justify-content:space-between; gap:.75rem; margin-top:4rem; padding:1.2rem 0; border-top:1px solid var(--line); color:var(--muted); font-size:.84rem; } footer a { text-decoration:none; font-weight:700; }
  @media(max-width:850px) { .grid,.cmd-grid { grid-template-columns:1fr; } .hero { grid-template-columns:1fr; } .hero-aside { max-width:460px; } }
  @media(max-width:620px) { .topbar { align-items:flex-start; flex-direction:column; gap:.35rem; padding:.7rem 1rem; } .nav { justify-content:flex-start; width:100%; overflow-x:auto; flex-wrap:nowrap; } .nav a { white-space:nowrap; } main { padding:1rem 1rem 3rem; } .hero { gap:1rem; padding:1.6rem 1.3rem; border-radius:19px; } .stats { grid-template-columns:1fr 1fr; margin-bottom:2.7rem; } .stat { padding:.8rem; } .section-heading { align-items:flex-start; flex-direction:column; } .page-section { margin:2.2rem 0; padding:1.1rem; border-radius:16px; } }
  @media(prefers-reduced-motion:reduce) { html { scroll-behavior:auto; } }
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#102a35">
<meta name="description" content="Week 6 VXLAN overlay lab: a multi-tenant data centre built from data, with flood-and-learn, isolation and MTU evidence.">
<title>Overlay {last4}: my data centre, from data</title>
<style>{css}</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="topbar">
  <a class="brand" href="../"><span class="brand-mark">W6</span>WIC2005 · Lab portfolio</a>
  <nav class="nav" aria-label="Page sections">
    <a href="#design">Design</a><a href="#vteps">VTEPs</a><a href="#evidence">Evidence</a><a href="#reflection">Reflection</a>
    <span class="sep" aria-hidden="true"></span>
    <a href="../">Week 1</a><a href="../week-02/">Week 2</a><a href="../week3/">Week 3</a>
  </nav>
</header>
<main id="main">
  <section class="hero" id="overview">
    <div class="hero-copy">
      <p class="eyebrow">Week 06 · VXLAN overlay · Mininet lab</p>
      <h1>My data centre overlay, from data</h1>
      <p id="summary">{n_hv} hypervisors and {n_tenants} tenants ({n_vms} VMs) on <code>{v4_block}</code>, joined by VXLAN.
Every tenant's MTU was checked against the underlay before anything was built.</p>
      <div class="hero-actions">
        <a class="button button-primary" href="#design">Explore the overlay <span aria-hidden="true">↓</span></a>
        <a class="button button-ghost" id="repository" href="{repo}">View repository <span aria-hidden="true">↗</span></a>
      </div>
    </div>
    <aside class="hero-aside" aria-label="Address block and page information">
      <span class="aside-label">IPv4 address block</span><strong class="block-value">{v4_block}</strong>
      <div class="hero-meta"><span>ID suffix · {last4}</span><span>Updated · {today}</span></div>
    </aside>
  </section>

  <section class="stats" aria-label="Overlay summary">
    <div class="stat"><strong>{n_hv}</strong><span>Hypervisors (VTEPs)</span></div>
    <div class="stat"><strong>{n_tenants}</strong><span>Tenants, one VNI each</span></div>
    <div class="stat"><strong>{n_vms}</strong><span>VMs</span></div>
    <div class="stat"><strong>{umtu}</strong><span>Underlay MTU</span></div>
  </section>

  <section class="page-section" id="design">
    <div class="section-heading"><div><p class="section-kicker">01 · The design</p><h2>Hypervisors and tenants</h2><p>Every address, MAC and VTEP below is worked out from the YAML file.</p></div><span class="section-index">{underlay}</span></div>
    <div class="grid">
      <article class="panel diagram-panel wide"><h3>Diagram</h3><div id="diagram">{diagram}</div></article>
      <article class="panel"><h3>Hypervisors and the underlay</h3><section id="hypervisors">{hypervisors}</section></article>
      <article class="panel"><h3>MTU plan: tenant packet + {overhead} bytes of VXLAN</h3><div id="mtu-plan">{mtu_plan}</div></article>
    </div>
    <section class="tenants" id="tenants">{tenants}</section>
    <aside class="callout"><span aria-hidden="true">↳</span><div><strong>Reading a MAC address</strong><p>Each VM's MAC is <code>02:VV:VV:VV:00:XX</code>. The highlighted middle three bytes are the tenant's VNI, and the last byte is the VM's address. Two VMs can share an IP address but never a MAC.</p></div></aside>
  </section>

  <section class="page-section" id="vteps">
    <div class="section-heading"><div><p class="section-kicker">02 · Tunnel endpoints</p><h2>VTEP commands, as built</h2><p>What <code>tenant_commands()</code> ran on each hypervisor: bridge, VXLAN device, VM ports, flood list.</p></div><span class="section-index">{n_cmds} commands</span></div>
    <section class="cmd-grid" id="commands">{commands}</section>
  </section>

  <section class="page-section" id="evidence">
    <div class="section-heading"><div><p class="section-kicker">03 · Live Mininet output</p><h2>Evidence from the running overlay</h2><p>Expand an item to see the captured command output.</p></div><span class="section-index">{n_evidence} records</span></div>
    <div class="evidence-list">{evidence}</div>
  </section>

  <section class="page-section" id="reflection">
    <div class="section-heading"><div><p class="section-kicker">04 · Lab notes</p><h2>What I learned</h2><p>Design, isolation, flooding, MTU and the P4 alternative.</p></div><span class="section-index">Reflection</span></div>
    <section class="answer-grid" id="answers">{answers}</section>
  </section>

  <footer><span>WIC2005 · Week 6 · generated from <code>{source}</code> by <code>make_page6.py</code> on {today}</span><a href="{repo}">Source repository ↗</a></footer>
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
                n_evidence=len(EVIDENCE),
                umtu=esc(spec["underlay"]["mtu"]),
                underlay=esc(spec["underlay"]["network"]),
                overhead=VXLAN_OVERHEAD,
                v4_block=f"10.{int(last4[2:])}.0.0/16",
                repo=esc(page.get("repository", "")),
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
