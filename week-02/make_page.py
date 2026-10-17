#!/usr/bin/env python3
"""Generate the Week 2 portfolio page from topology, answers, and evidence."""

from __future__ import annotations

import html
import sys
from pathlib import Path

from build_topo import check, load


LAB_DIR = Path(__file__).resolve().parent
REPO_DIR = LAB_DIR.parent
EVIDENCE = ("check.txt", "pingall.txt", "neigh.txt", "macs.txt", "dad.txt")


def load_page_data(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required (it is included in the course container).") from exc
    with path.open(encoding="utf-8") as source:
        return yaml.safe_load(source) or {}


def links_section(topology: dict) -> str:
    """Build an HTML list with every topology link."""
    links = topology.get("links", [])
    rows = "\n".join(
        f"<li><code>{html.escape(str(left))} — {html.escape(str(right))}</code></li>"
        for left, right in links
    )
    return f"<ul class=\"links\">\n{rows}\n</ul>"


def mermaid_diagram(topology: dict) -> str:
    """Return Mermaid flowchart text, one edge for every link in the topology."""
    return "graph LR\n" + "\n".join(f"  {left} --- {right}" for left, right in topology.get("links", []))


def evidence_section() -> str:
    blocks: list[str] = []
    for filename in EVIDENCE:
        path = LAB_DIR / "evidence" / filename
        if path.is_file() and path.stat().st_size:
            contents = html.escape(path.read_text(encoding="utf-8", errors="replace"))
            state = "Collected"
            body = f"<pre>{contents}</pre>"
        else:
            state = "Missing"
            body = "<p class=\"missing\">Collect this output by following the A3/A4 steps in the lab README.</p>"
            print(f"WARNING: evidence/{filename} is missing or empty")
        blocks.append(
            f"<details><summary>{html.escape(filename)} — {state}</summary>{body}</details>"
        )
    return "\n".join(blocks)


def main() -> int:
    try:
        topology = load(LAB_DIR / "topology.yaml")
        problems = check(topology)
        if problems:
            for problem in problems:
                print(f"PROBLEM: {problem}")
            return 1
        page = load_page_data(LAB_DIR / "page.yaml")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"PROBLEM: {exc}")
        return 1

    hosts = "\n".join(
        "<tr><td>{}</td><td><code>{}</code></td><td><code>{}</code></td></tr>".format(
            html.escape(host["name"]), html.escape(host["ip"]), html.escape(host["ipv6"])
        )
        for host in topology["hosts"]
    )
    answers = page.get("answers", {})
    answer_blocks = "\n".join(
        f"<section><h2>{title}</h2><p>{html.escape(str(answers.get(key, '')))}</p></section>"
        for key, title in (
            ("network", "My network"),
            ("data_model", "Data model and serialization"),
            ("evidence", "What the evidence shows"),
            ("version_control", "Why Git diff helps"),
        )
    )
    repository = html.escape(str(page.get("repository", "")))
    diagram = html.escape(mermaid_diagram(topology))
    output = REPO_DIR / "docs" / "week-02" / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>WIC2005 Week 2 | Networks as Data</title>
<style>
:root{color-scheme:light;--ink:#172033;--muted:#526071;--accent:#126782;--paper:#fff;--line:#d8e1e8}
*{box-sizing:border-box}body{margin:0;background:#f3f7f9;color:var(--ink);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:auto;padding:28px 20px 60px}header,section{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:24px;margin:18px 0;box-shadow:0 4px 18px #17324a0d}
h1{font-size:clamp(2rem,5vw,3.2rem);margin:.1em 0}h2{color:var(--accent);margin-top:0}.tag{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase}
a{color:var(--accent);font-weight:650}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line)}
code,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}pre{white-space:pre-wrap;overflow:auto;background:#111827;color:#e7edf4;padding:16px;border-radius:9px}
.missing{color:#9b3d26}details{background:#f8fbfc;border:1px solid var(--line);border-radius:8px;padding:12px;margin:10px 0}summary{cursor:pointer;font-weight:650}.links{columns:2}
</style></head><body><main>
<header><div class="tag">WIC2005 Programmable Networks · matric suffix 4903</div><h1>Week 2: Networks as Data</h1>
<p>A checked topology description builds the Mininet network and supplies this page.</p><p><a href="../../">Portfolio home</a> · <a href="REPOSITORY">Repository</a></p></header>
<section><h2>Topology</h2><p>Three Linux bridges and six dual-stack hosts.</p><div class="mermaid">DIAGRAM</div></section>
<section><h2>Host addresses</h2><table><thead><tr><th>Host</th><th>IPv4</th><th>IPv6</th></tr></thead><tbody>HOST_ROWS</tbody></table></section>
<section><h2>Every link</h2>LINKS</section>
<section><h2>Experiment evidence</h2><p>Evidence files are copied from the running Mininet experiment.</p>EVIDENCE</section>
ANSWERS
</main><script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script><script>mermaid.initialize({startOnLoad:true,theme:'neutral'});</script></body></html>
""".replace("DIAGRAM", diagram)
        .replace("HOST_ROWS", hosts)
        .replace("LINKS", links_section(topology))
        .replace("EVIDENCE", evidence_section())
        .replace("ANSWERS", answer_blocks)
        .replace("REPOSITORY", repository),
        encoding="utf-8",
    )
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
