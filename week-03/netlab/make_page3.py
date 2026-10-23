#!/usr/bin/env python3
"""Week 3 assignment: generate your routed network's page from network.yaml.

Run it inside the lab container, from your netlab folder:
    python3 make_page3.py network.yaml

It checks network.yaml with the same checks as build_routed.py (including your check_paths()),
so a network with a loop or a missing route never gets published, then writes
docs/week3/index.html with your network, your evidence (evidence3/) and your answers
(page3.yaml). GitHub Pages publishes it at https://<you>.github.io/<repository>/week3/

The page includes a routing table for each router, generated from the network data.
"""
import datetime
import html
import ipaddress  # for routing_tables_section()
import json
import os
import sys
from pathlib import Path

import yaml

from build_routed import check_paths, check_spec, hosts, load, plan

NETLAB = Path(__file__).resolve().parent
REPO = NETLAB.parent.parent
EVIDENCE = [
    ("routes", "evidence3/routes.txt", "Every router's routing table: ip route"),
    ("traces", "evidence3/traces.txt", "Traceroutes from h1 to each remote LAN"),
    ("connectivity", "evidence3/connectivity.txt", "All 12 directed host-to-host pings"),
    ("summary", "evidence3/summary.txt", "r3 summary-route lookups"),
    ("lpm", "evidence3/lpm.txt", "r1 longest-prefix-match lookups"),
    ("failure", "evidence3/failure.txt", "A link goes down: what static routes do"),
    ("check", "evidence3/check.txt", "check_paths() stopping a loop and a missing route"),
]


def esc(text):
    return html.escape(str(text))


def lans_section(spec):
    rows = "".join(
        f"<tr><td>{esc(l['name'])}</td><td><code>{esc(l['network'])}</code></td><td>{esc(l['router'])}</td>"
        f"<td>{esc(l['host'])} <code>{esc(hosts(spec)[l['host']][0])}</code></td></tr>"
        for l in spec["lans"]
    )
    return f"<table><thead><tr><th>LAN</th><th>Network</th><th>Router (.1)</th><th>Host (.10)</th></tr></thead><tbody>{rows}</tbody></table>"


def links_section(spec):
    rows = "".join(
        f"<tr><td>{esc(a)} — {esc(b)}</td><td><code>{esc(n)}</code></td></tr>" for a, b, n in spec["links"]
    )
    return f"<table><thead><tr><th>Link</th><th>Network</th></tr></thead><tbody>{rows}</tbody></table>"


def routing_tables_section(spec):
    """Return HTML showing each router's routing table, as the router sees it.

    For each router in spec["routers"], list:
      - its directly connected networks: plan(spec)[router] gives its interfaces;
        each one's .network is a connected network
      - its static routes: spec["routes"].get(router), each with "to" and "via"
    sorted longest prefix first (the order in which longest-prefix match prefers them).
    Show each entry's destination and where it goes ("directly connected", or the next hop).
    For example, one table per router:
        <h3>r1</h3><table><tr><th>Destination</th><th>Next hop</th></tr>
        <tr><td>10.7.12.0/30</td><td>directly connected</td></tr> ...</table>
    Use esc() on every value.
    """
    sections = []
    interfaces = plan(spec)
    for router in spec["routers"]:
        entries = [(intf.network, "directly connected") for intf in interfaces[router]]
        entries += [
            (ipaddress.ip_network(route["to"]), str(ipaddress.ip_address(route["via"])))
            for route in (spec.get("routes") or {}).get(router, []) or []
        ]
        entries.sort(key=lambda item: (-item[0].prefixlen, int(item[0].network_address)))
        rows = "".join(
            f"<tr><td><code>{esc(destination)}</code></td><td>"
            f"<span class=\"hop {'connected' if next_hop == 'directly connected' else 'static'}\">{esc(next_hop)}</span></td></tr>"
            for destination, next_hop in entries
        )
        sections.append(
            f"<article class=\"route-card\"><header><span class=\"router-mark\">ROUTER</span>"
            f"<h3>{esc(router)}</h3></header><div class=\"table-wrap\"><table>"
            f"<thead><tr><th>Destination</th><th>Next hop</th></tr></thead><tbody>{rows}</tbody>"
            f"</table></div></article>"
        )
    return "\n".join(sections)


def topology_svg(spec):
    """Draw the Week 3 topology with straight links that stop at node borders."""
    host_data = hosts(spec)
    lan_networks = {lan["host"]: lan["network"] for lan in spec["lans"]}
    link_networks = {frozenset((a, b)): network for a, b, network in spec["links"]}

    def host_node(host, x, y, width=140, height=78):
        address, _router = host_data[host]
        network = lan_networks[host]
        center = x + width / 2
        return (
            f'<g class="topology-host"><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="12" />'
            f'<text class="topology-host-name" x="{center}" y="{y + 25}">{esc(host)}</text>'
            f'<text class="topology-host-meta" x="{center}" y="{y + 44}">{esc(address)}</text>'
            f'<text class="topology-host-meta" x="{center}" y="{y + 62}">{esc(network)}</text></g>'
        )

    def router_node(router, x, y):
        return (
            f'<g class="topology-router"><rect x="{x}" y="{y}" width="130" height="64" rx="13" />'
            f'<text x="{x + 65}" y="{y + 28}">{esc(router)}</text>'
            f'<text class="topology-router-meta" x="{x + 65}" y="{y + 46}">router</text></g>'
        )

    # Fixed positions keep the redundant r1-r2-r3 path readable and preserve
    # the four-LAN layout while all connection and address labels come from YAML.
    nodes = {
        "r1": (210, 210),
        "r2": (470, 210),
        "r3": (330, 370),
        "r4": (720, 210),
    }
    hosts_at = {
        "h1": (20, 203, 140, 78),
        "h2": (465, 48, 140, 78),
        "h3": (650, 310, 140, 78),
        "h4": (890, 203, 140, 78),
    }

    def link(a, b, x1, y1, x2, y2, lx, ly, kind="router-link"):
        network = link_networks[frozenset((a, b))]
        return (
            f'<line class="{kind}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" />'
            f'<text class="topology-link-label" x="{lx}" y="{ly}">{esc(network)}</text>'
        )

    lines = [
        '<svg class="topology-svg" viewBox="0 0 1050 470" role="img" aria-labelledby="topology-title topology-description">',
        '<title id="topology-title">Four-router, four-LAN network topology</title>',
        '<desc id="topology-description">Routers r1, r2, and r3 form a redundant triangle; r2 connects to r4. Each host connects to its LAN router.</desc>',
        '<g aria-hidden="true">',
        link("r1", "r2", 340, 242, 470, 242, 405, 222),
        link("r1", "r3", 315, 274, 370, 370, 310, 326),
        link("r3", "r2", 450, 370, 490, 274, 465, 326),
        link("r2", "r4", 600, 242, 720, 242, 660, 222),
        '<line class="lan-link" x1="160" y1="242" x2="210" y2="242" />',
        '<line class="lan-link" x1="535" y1="126" x2="535" y2="210" />',
        '<line class="lan-link" x1="590" y1="274" x2="650" y2="349" />',
        '<line class="lan-link" x1="850" y1="242" x2="890" y2="242" />',
        '</g>',
        host_node("h1", *hosts_at["h1"]),
        host_node("h2", *hosts_at["h2"]),
        host_node("h3", *hosts_at["h3"]),
        host_node("h4", *hosts_at["h4"]),
        *(router_node(router, *nodes[router]) for router in ("r1", "r2", "r3", "r4")),
        '</svg>',
    ]
    return "\n".join(lines)


def evidence_section(ev_id, path, title):
    evidence_path = NETLAB / path
    if evidence_path.exists() and evidence_path.read_text().strip():
        output = "\n".join(line.rstrip() for line in evidence_path.read_text().splitlines())
        body = f'<pre id="evidence-{ev_id}">{esc(output)}</pre>'
    else:
        print(f"WARNING: {path} is missing or empty")
        body = f'<pre id="evidence-{ev_id}" class="missing">Missing: {esc(path)}</pre>'
    return (
        f'<details class="evidence-card" id="evidence-card-{ev_id}">'
        f'<summary><span class="evidence-title">{esc(title)}</span>'
        f'<span class="file">{esc(path)}</span></summary>{body}</details>'
    )


def answers_section(page):
    parts = []
    for key, qa in page.get("answers", {}).items():
        answer = str(qa.get("answer") or "").strip()
        if not answer:
            print(f"WARNING: page3.yaml has no answer for '{key}'")
            answer = "(Not answered yet.)"
        paragraphs = "".join(f"<p>{esc(p.strip())}</p>" for p in answer.split("\n\n") if p.strip())
        parts.append(
            f'<article class="answer-card" id="answer-{esc(key)}">'
            f'<span class="answer-key">{esc(key.replace("_", " "))}</span>'
            f'<h3>{esc(qa.get("question", key))}</h3>{paragraphs}</article>'
        )
    return "\n".join(parts)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#102a35">
<meta name="description" content="Week 3 routed Mininet lab: topology, static routes, live traces and failure evidence.">
<title>Week 3 · Routed Network Lab</title>
<style>
  :root {{ color-scheme: light; --ink:#142b33; --muted:#617780; --teal:#087e83; --teal-dark:#075c64; --lime:#c6f36a; --paper:#fff; --canvas:#e7f0ec; --line:#d5e2dc; --navy:#102a35; --shadow:0 18px 48px #163c3b12; }}
  * {{ box-sizing:border-box; }} html {{ scroll-behavior:smooth; scroll-padding-top:5.5rem; }}
  body {{ margin:0; background:radial-gradient(ellipse at 12% 18%,#d4e9e1 0,transparent 38%),linear-gradient(180deg,#e4efea 0,#f3f6f2 36rem,#eef3f0 100%); color:var(--ink); font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  a {{ color:var(--teal-dark); }} a:focus-visible, summary:focus-visible {{ outline:3px solid #dc8d27; outline-offset:3px; border-radius:4px; }}
  .skip-link {{ position:absolute; left:-9999px; top:1rem; z-index:20; background:#fff; padding:.7rem 1rem; }} .skip-link:focus {{ left:1rem; }}
  .topbar {{ position:sticky; top:0; z-index:10; display:flex; align-items:center; justify-content:space-between; gap:1.5rem; padding:.75rem max(1.25rem,calc((100% - 1160px)/2)); background:#102a35f5; color:#eff8f3; backdrop-filter:blur(14px); }}
  .brand {{ color:#eff8f3; text-decoration:none; font-weight:750; letter-spacing:.02em; white-space:nowrap; }} .brand-mark {{ display:inline-grid; place-items:center; width:2rem; height:2rem; margin-right:.55rem; border-radius:9px; background:var(--lime); color:var(--navy); font-size:.78rem; }}
  .nav {{ display:flex; flex-wrap:wrap; justify-content:flex-end; gap:.25rem; }} .nav a {{ color:#c4d9d4; padding:.45rem .65rem; font-size:.88rem; text-decoration:none; border-radius:8px; }} .nav a:hover {{ color:#fff; background:#ffffff18; }}
  main {{ max-width:1160px; margin:auto; padding:2rem 1.25rem 4rem; }}
  .hero {{ position:relative; overflow:hidden; display:grid; grid-template-columns:minmax(0,1.5fr) minmax(250px,.7fr); gap:2rem; padding:clamp(2rem,5vw,4.25rem); border-radius:26px; color:#f2faf5; background:radial-gradient(circle at 91% 10%,#247e78 0,transparent 34%),linear-gradient(125deg,#102a35 5%,#15444b 70%,#0e625f); box-shadow:var(--shadow); }}
  .hero:after {{ content:""; position:absolute; width:330px; height:330px; right:-140px; bottom:-220px; border:1px solid #ffffff24; border-radius:50%; box-shadow:0 0 0 35px #ffffff09,0 0 0 70px #ffffff06; pointer-events:none; }}
  .eyebrow,.section-kicker {{ margin:0 0 .6rem; color:var(--teal); font-size:.75rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }} .hero .eyebrow {{ color:var(--lime); }}
  h1 {{ max-width:700px; margin:.1rem 0 1rem; font-size:clamp(2.5rem,6vw,4.6rem); line-height:1.02; letter-spacing:-.055em; }} .hero-copy>p:not(.eyebrow) {{ max-width:650px; color:#d3e5df; font-size:1.08rem; }}
  .hero-actions {{ display:flex; flex-wrap:wrap; gap:.7rem; margin-top:1.5rem; }} .button {{ display:inline-flex; align-items:center; gap:.55rem; padding:.7rem 1rem; border-radius:10px; font-weight:750; text-decoration:none; }} .button-primary {{ background:var(--lime); color:var(--navy); }} .button-ghost {{ border:1px solid #ffffff50; color:#f2faf5; }}
  .hero-aside {{ align-self:end; position:relative; z-index:1; padding:1.15rem; border:1px solid #ffffff28; border-radius:16px; background:#ffffff0c; backdrop-filter:blur(8px); }} .aside-label {{ color:#a9c6bd; font-size:.76rem; text-transform:uppercase; letter-spacing:.1em; }} .block-value {{ display:block; margin:.2rem 0 .8rem; color:#fff; font:700 clamp(1.35rem,3vw,1.8rem)/1.2 ui-monospace,monospace; }} .hero-meta {{ display:flex; justify-content:space-between; gap:1rem; padding-top:.75rem; border-top:1px solid #ffffff25; color:#c6d9d3; font-size:.82rem; }}
  .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:.85rem; margin:1.1rem 0 3.5rem; }} .stat {{ padding:1rem 1.15rem; border:1px solid #d3e1da; border-radius:14px; background:#d9ece4; box-shadow:0 8px 25px #163c3b08; }} .stat:nth-child(2) {{ background:#dcecf0; }} .stat:nth-child(3) {{ background:#e8e5f2; }} .stat:nth-child(4) {{ background:#f4ead4; }} .stat strong {{ display:block; color:var(--teal-dark); font-size:1.65rem; line-height:1.15; }} .stat span {{ color:#4f6870; font-size:.84rem; }}
  .page-section {{ margin:3.2rem 0; padding:clamp(1.25rem,3vw,2rem); border:1px solid #d3e1da; border-radius:22px; background:linear-gradient(145deg,#ffffff,#eaf5ef); box-shadow:var(--shadow); scroll-margin-top:5rem; }} #routes {{ background:linear-gradient(145deg,#e5ebf8,#f4f5fb); border-color:#d6deef; }} #evidence {{ background:linear-gradient(145deg,#dcefeb,#f0f8f5); border-color:#cfe2dc; }} #reflection {{ background:linear-gradient(145deg,#f3ead9,#fcf8ed); border-color:#eadfc8; }} .section-heading {{ display:flex; align-items:end; justify-content:space-between; gap:1rem; margin-bottom:1.2rem; padding-bottom:1rem; border-bottom:1px solid #ccded5; }} #routes .section-heading {{ border-color:#d5dcee; }} #evidence .section-heading {{ border-color:#cfe2dc; }} #reflection .section-heading {{ border-color:#e8dcc3; }} .section-heading h2 {{ margin:0; font-size:clamp(1.8rem,4vw,2.45rem); letter-spacing:-.04em; }} .section-heading p:not(.section-kicker) {{ margin:.35rem 0 0; color:var(--muted); }} .section-kicker {{ display:inline-block; padding:.22rem .5rem; border-radius:999px; background:#dcefe5; }} #routes .section-kicker {{ background:#e0e5f3; color:#4b5b91; }} #evidence .section-kicker {{ background:#d2eae3; }} #reflection .section-kicker {{ background:#efe1c4; color:#806322; }} .section-index {{ flex:none; padding:.35rem .6rem; border:1px solid #d1e0d8; border-radius:8px; background:#f8fcf9; color:#53756b; font:700 .78rem ui-monospace,monospace; }}
  .network-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; align-items:start; }} .panel,.route-card,.answer-card,.evidence-card {{ border:1px solid var(--line); border-radius:17px; background:var(--paper); box-shadow:0 10px 30px #163c3b08; }} .panel {{ padding:1.15rem; }} .panel h3 {{ margin:.2rem 0 .9rem; font-size:1rem; }} .diagram-panel {{ grid-column:1/-1; overflow-x:auto; padding:1.25rem; background:linear-gradient(145deg,#e6f3ee,#f7faf5); }} .topology-svg {{ display:block; width:100%; min-width:640px; height:auto; }} .topology-svg .router-link {{ stroke:#2c7773; stroke-width:3; stroke-linecap:butt; }} .topology-svg .lan-link {{ stroke:#678b81; stroke-width:2.5; stroke-linecap:butt; }} .topology-svg .topology-link-label {{ fill:#315f5b; stroke:#f3f8f4; stroke-width:5px; paint-order:stroke; stroke-linejoin:round; text-anchor:middle; font:700 12px ui-monospace,SFMono-Regular,Consolas,monospace; }} .topology-svg .topology-host rect {{ fill:#fff; stroke:#9dbbb0; stroke-width:2; }} .topology-svg .topology-host-name {{ fill:#163c3b; text-anchor:middle; font:800 14px system-ui,sans-serif; }} .topology-svg .topology-host-meta {{ fill:#536d69; text-anchor:middle; font:11px ui-monospace,SFMono-Regular,Consolas,monospace; }} .topology-svg .topology-router rect {{ fill:#e0f0e9; stroke:#28766e; stroke-width:2.5; }} .topology-svg .topology-router text {{ fill:#174e4a; text-anchor:middle; font:800 19px system-ui,sans-serif; }} .topology-svg .topology-router .topology-router-meta {{ fill:#567a72; font:10px system-ui,sans-serif; letter-spacing:.08em; text-transform:uppercase; }} .diagram-note {{ margin:.25rem 0 0; color:var(--muted); font-size:.82rem; }}
  .table-wrap {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; font-size:.9rem; }} th,td {{ padding:.72rem .65rem; border-bottom:1px solid #eaf0ed; text-align:left; vertical-align:top; }} th {{ color:var(--muted); font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; }} tbody tr:last-child td {{ border-bottom:0; }} td code, code {{ color:#135c60; font:600 .9em ui-monospace,SFMono-Regular,Consolas,monospace; overflow-wrap:anywhere; }}
  .route-intro {{ display:flex; flex-wrap:wrap; gap:.6rem; margin:0 0 1rem; }} .pill {{ display:inline-flex; align-items:center; gap:.4rem; padding:.35rem .65rem; border-radius:999px; background:#e3f2eb; color:#236551; font-size:.78rem; font-weight:750; }} .pill-summary {{ background:#f3eddb; color:#7a5c21; }} .route-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; }} .route-card {{ overflow:hidden; }} .route-card header {{ display:flex; align-items:center; gap:.65rem; padding:1rem 1rem .65rem; }} .route-card header h3 {{ margin:0; font-size:1.2rem; }} .router-mark {{ padding:.22rem .4rem; border-radius:6px; background:#e7f2ed; color:#387563; font-size:.62rem; font-weight:800; letter-spacing:.1em; }} .route-card .table-wrap {{ padding:0 .75rem .65rem; }} .route-card th,.route-card td {{ padding:.62rem .35rem; }} .hop {{ display:inline-block; padding:.24rem .45rem; border-radius:6px; font-size:.78rem; }} .connected {{ background:#e8f2ed; color:#356951; }} .static {{ background:#edf0f9; color:#4b5b91; font-family:ui-monospace,monospace; }}
  .summary-callout {{ display:flex; gap:.9rem; align-items:flex-start; margin-top:1rem; padding:1rem 1.1rem; border:1px solid #e9dfc5; border-radius:13px; background:#fbf7ec; color:#5b4d2b; }} .summary-callout strong {{ display:block; color:#624d1d; }} .summary-callout p {{ margin:.15rem 0 0; font-size:.9rem; }}
  .evidence-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.8rem; }} .evidence-card {{ overflow:hidden; }} .evidence-card summary {{ display:flex; flex-direction:column; gap:.15rem; padding:1rem 1.1rem; cursor:pointer; list-style:none; }} .evidence-card summary::-webkit-details-marker {{ display:none; }} .evidence-card summary:after {{ content:"+"; position:absolute; right:1.1rem; top:1rem; color:var(--teal); font-size:1.15rem; font-weight:700; }} .evidence-card summary {{ position:relative; padding-right:2.6rem; }} .evidence-card[open] summary:after {{ content:"−"; }} .evidence-title {{ color:var(--ink); font-weight:750; }} .file {{ color:var(--muted); font: .75rem ui-monospace,monospace; }} pre {{ max-height:380px; overflow:auto; margin:0; padding:1rem 1.1rem; border-top:1px solid #e6eeea; background:#102a35; color:#dcece5; font: .78rem/1.55 ui-monospace,SFMono-Regular,Consolas,monospace; white-space:pre-wrap; overflow-wrap:anywhere; }} pre.missing {{ background:#fff1ec; color:#8b4027; }}
  .answer-grid {{ display:grid; gap:.8rem; }} .answer-card {{ padding:1.15rem 1.3rem; }} .answer-key {{ color:var(--teal); font-size:.72rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }} .answer-card h3 {{ margin:.35rem 0 .65rem; font-size:1.08rem; line-height:1.4; }} .answer-card p {{ margin:.55rem 0 0; color:#425960; }}
  footer {{ display:flex; flex-wrap:wrap; justify-content:space-between; gap:.75rem; margin-top:4rem; padding:1.2rem 0; border-top:1px solid var(--line); color:var(--muted); font-size:.84rem; }} footer a {{ text-decoration:none; font-weight:700; }}
  @media(max-width:850px) {{ .network-grid {{ grid-template-columns:1fr; }} .route-grid {{ grid-template-columns:1fr 1fr; }} .hero {{ grid-template-columns:1fr; }} .hero-aside {{ max-width:460px; }} }}
  @media(max-width:620px) {{ .topbar {{ align-items:flex-start; flex-direction:column; gap:.35rem; padding:.7rem 1rem; }} .nav {{ justify-content:flex-start; width:100%; overflow-x:auto; flex-wrap:nowrap; }} .nav a {{ white-space:nowrap; }} main {{ padding:1rem .8rem 3rem; }} .hero {{ gap:1rem; padding:1.6rem 1.3rem; border-radius:19px; }} .stats {{ grid-template-columns:1fr 1fr; margin-bottom:2.7rem; }} .stat {{ padding:.8rem; }} .section-heading {{ align-items:flex-start; }} .route-grid,.evidence-grid {{ grid-template-columns:1fr; }} .page-section {{ margin:2.2rem 0; padding:1.1rem; border-radius:16px; }} }}
  @media(prefers-reduced-motion:reduce) {{ html {{ scroll-behavior:auto; }} * {{ animation-duration:.01ms!important; transition-duration:.01ms!important; }} }}
</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="topbar">
  <a class="brand" href="../"><span class="brand-mark">W3</span>WIC2005 · Lab portfolio</a>
  <nav class="nav" aria-label="Page sections">
    <a href="#topology">Topology</a><a href="#routes">Routing</a><a href="#evidence">Evidence</a><a href="#reflection">Reflection</a>
  </nav>
</header>
<main id="main">
  <section class="hero" id="overview">
    <div class="hero-copy">
      <p class="eyebrow">Week 03 · Static routing · Mininet lab</p>
      <h1>A small network.<br>A clear route.</h1>
      <p>{topology_copy}</p>
      <div class="hero-actions">
        <a class="button button-primary" href="#topology">Explore the network <span aria-hidden="true">↓</span></a>
        <a class="button button-ghost" id="repository" href="{repo}">View repository <span aria-hidden="true">↗</span></a>
      </div>
    </div>
    <aside class="hero-aside" aria-label="Address block and page information">
      <span class="aside-label">IPv4 address block</span><strong class="block-value">{v4_block}</strong>
      <div class="hero-meta"><span>ID suffix · {last4}</span><span>Updated · {today}</span></div>
    </aside>
  </section>

  <section class="stats" aria-label="Network summary">
    <div class="stat"><strong>{n_routers}</strong><span>Linux routers</span></div>
    <div class="stat"><strong>{n_lans}</strong><span>Host LANs</span></div>
    <div class="stat"><strong>{n_links}</strong><span>Router links</span></div>
    <div class="stat"><strong>{n_routes}</strong><span>Static routes</span></div>
  </section>

  <section class="page-section" id="topology">
    <div class="section-heading"><div><p class="section-kicker">01 · Network design</p><h2>Topology</h2><p>Two paths connect r1 and r2; h2 and h3 use separate LANs on r2, while h4 is on r4.</p></div><span class="section-index">{v4_block}</span></div>
    <div class="network-grid">
      <article class="panel diagram-panel"><h3>Logical layout</h3><div id="diagram">{diagram}</div><p class="diagram-note">Straight lines stop at each device; labels identify the /30 router links and /24 host LANs.</p></article>
      <article class="panel"><h3>Host LANs</h3><div id="lans">{lans}</div></article>
      <article class="panel"><h3>Router links</h3><div id="links">{links}</div></article>
    </div>
  </section>

  <section class="page-section" id="routes">
    <div class="section-heading"><div><p class="section-kicker">02 · Forwarding</p><h2>Routing tables</h2><p>Connected networks and configured static routes, sorted by longest prefix first.</p></div><span class="section-index">{n_routes} static · {n_table_entries} total</span></div>
    <div class="route-intro"><span class="pill">Directly connected</span><span class="pill pill-summary">Static next hop</span></div>
    <div class="route-grid" id="routing-tables">{tables}</div>
    <aside class="summary-callout"><span aria-hidden="true">↳</span><div><strong>Longest-prefix match in action</strong><p>r1 uses <code>{r1_h2_route}</code> for h2. Its <code>10.{nn}.32.0/20</code> summary sends h3 and h4 through r3. On r3, h2, h3 and h4 all use the same summary next hop, r2.</p></div></aside>
  </section>

  <section class="page-section" id="evidence">
    <div class="section-heading"><div><p class="section-kicker">03 · Live Mininet output</p><h2>Evidence</h2><p>Expand an item to inspect the captured command output.</p></div><span class="section-index">{n_evidence} records</span></div>
    <div class="evidence-grid">{evidence}</div>
  </section>

  <section class="page-section" id="reflection">
    <div class="section-heading"><div><p class="section-kicker">04 · Lab notes</p><h2>What I learned</h2><p>Design choices, route summaries, failure behavior and control-plane work.</p></div><span class="section-index">Reflection</span></div>
    <div class="answer-grid" id="answers">{answers}</div>
  </section>

  <footer><span>WIC2005 · Week 3 · generated from <code>{source}</code></span><a href="{repo}">Source repository ↗</a></footer>
</main>

<script type="application/json" id="network-data">{data}</script>
</body>
</html>
"""


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 make_page3.py <network.yaml>")
    source = sys.argv[1]
    spec = load(source)
    problems = check_spec(spec)
    if not problems:
        problems = check_paths(spec)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        sys.exit("Fix the description first: a network with problems doesn't get published.")

    with open(NETLAB / "page3.yaml") as f:
        page = yaml.safe_load(f)
    last4 = str(spec["student_id_last4"])
    output = REPO / "docs" / "week3"
    output.mkdir(parents=True, exist_ok=True)
    with open(output / "index.html", "w", encoding="utf-8") as f:
        f.write(
            PAGE.format(
                last4=esc(last4),
                source=esc(source),
                today=datetime.date.today().isoformat(),
                n_routers=len(spec["routers"]),
                n_lans=len(spec["lans"]),
                n_links=len(spec["links"]),
                n_routes=sum(len(v or []) for v in (spec.get("routes") or {}).values()),
                n_table_entries=sum(len(plan(spec)[router]) for router in spec["routers"]) + sum(len(v or []) for v in (spec.get("routes") or {}).values()),
                n_evidence=len(EVIDENCE),
                topology_copy=f"{len(spec['routers'])} routers connect {len(spec['lans'])} host LANs over {len(spec['links'])} router links. Static routes expose a redundant path and make longest-prefix matching and link-failure behavior visible.",
                r1_h2_route="10.{}.32.0/24 via 10.{}.12.2".format(int(last4[2:]), int(last4[2:])),
                nn=int(last4[2:]),
                v4_block=f"10.{int(last4[2:])}.0.0/16",
                repo=esc(page.get("repository", "")),
                lans=lans_section(spec),
                links=links_section(spec),
                diagram=topology_svg(spec),
                tables=routing_tables_section(spec),
                evidence="\n".join(evidence_section(*e) for e in EVIDENCE),
                answers=answers_section(page),
                data=json.dumps(spec, indent=2).replace("</", "<\\/"),
            )
        )
    print("Wrote docs/week3/index.html")


if __name__ == "__main__":
    main()
