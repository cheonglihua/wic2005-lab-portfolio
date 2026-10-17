#!/usr/bin/env python3
"""Generate the Week 2 portfolio page from topology, answers, and evidence."""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

from build_topo import check, load


LAB_DIR = Path(__file__).resolve().parent
REPO_DIR = LAB_DIR.parent
EVIDENCE = ("check.txt", "pingall.txt", "neigh.txt", "macs.txt", "dad.txt")


def load_page_data(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required (it is included in the course container).") from exc
    try:
        with path.open(encoding="utf-8") as source:
            data = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: malformed YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping containing repository and answers")
    return data


def links_section(topology: dict) -> str:
    """Build an HTML list with every topology link."""
    links = topology.get("links", [])
    rows = "\n".join(
        f"<li><code>{html.escape(str(left))} — {html.escape(str(right))}</code></li>"
        for left, right in links
    )
    return f"<ul class=\"links\">\n{rows}\n</ul>"


def mermaid_diagram(topology: dict) -> str:
    """Return a core/access Mermaid flowchart with every data link exactly once."""
    switches = topology.get("switches", [])
    hosts = {host["name"] for host in topology.get("hosts", [])}
    switch_set = set(switches)
    labels = topology.get("switch_labels", {})
    links = topology.get("links", [])
    core = next(
        (switch for switch in switches if str(labels.get(switch, "")).casefold() == "core"),
        None,
    )

    ordered_links: list[tuple[str, str]] = []
    if core:
        access_switches = [
            switch
            for switch in switches
            if switch != core
            and any(set(link) == {core, switch} for link in links)
        ]
        used: set[int] = set()
        for position, access in enumerate(access_switches):
            host_links = [
                (index, link)
                for index, link in enumerate(links)
                if access in link and any(node in hosts for node in link)
            ]
            core_links = [
                (index, link)
                for index, link in enumerate(links)
                if set(link) == {core, access}
            ]

            def add_hosts() -> None:
                for index, link in host_links:
                    host = next(node for node in link if node in hosts)
                    ordered_links.append((host, access))
                    used.add(index)

            if position == 0:
                add_hosts()
            for index, _link in core_links:
                ordered_links.append((access, core) if position == 0 else (core, access))
                used.add(index)
            if position > 0:
                add_hosts()
        ordered_links.extend(
            (left, right) for index, (left, right) in enumerate(links) if index not in used
        )
    else:
        ordered_links = [(left, right) for left, right in links]

    def node_reference(node: str, declared: set[str]) -> str:
        if node in switch_set and node not in declared:
            declared.add(node)
            label = str(labels.get(node, node)).replace('"', "'")
            return f'{node}["{node} · {label}"]'
        if node in hosts:
            return f"{node}[{node}]"
        return node

    lines = ["graph LR"]
    declared: set[str] = set()
    for left, right in ordered_links:
        lines.append(f"  {node_reference(left, declared)} --- {node_reference(right, declared)}")
    return "\n".join(lines)


def evidence_section() -> str:
    blocks: list[str] = []
    for filename in EVIDENCE:
        path = LAB_DIR / "evidence" / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"required evidence file is missing or empty: {path}")
        contents = html.escape(path.read_text(encoding="utf-8", errors="replace"))
        body = f"<pre>{contents}</pre>"
        blocks.append(
            f"<details><summary>{html.escape(filename)} — Collected</summary>{body}</details>"
        )
    return "\n".join(blocks)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "topology",
        nargs="?",
        type=Path,
        help="YAML or JSON topology (default: topology.yaml beside this script)",
    )
    args = parser.parse_args(argv)
    topology_path = args.topology or (LAB_DIR / "topology.yaml")
    if not topology_path.is_absolute():
        topology_path = Path.cwd() / topology_path
    topology_path = topology_path.resolve()
    if not topology_path.is_file():
        print(f"PROBLEM: topology file not found: {topology_path}")
        return 1

    try:
        topology = load(topology_path)
        problems = check(topology)
        if problems:
            for problem in problems:
                print(f"PROBLEM: {problem}")
            return 1
        page = load_page_data(LAB_DIR / "page.yaml")
        answers = page.get("answers")
        if not isinstance(answers, dict):
            raise ValueError(f"{LAB_DIR / 'page.yaml'}: answers must be a mapping")
        required_answers = ("network", "data_model", "version_control")
        for key in required_answers:
            if not isinstance(answers.get(key), str) or not answers[key].strip():
                raise ValueError(f"{LAB_DIR / 'page.yaml'}: answer '{key}' is missing or empty")
        evidence_answer = answers.get("evidence")
        if not isinstance(evidence_answer, list) or not evidence_answer or any(
            not isinstance(point, str) or not point.strip() for point in evidence_answer
        ):
            raise ValueError(f"{LAB_DIR / 'page.yaml'}: answer 'evidence' must be a non-empty list of points")
        repository_url = page.get("repository")
        parsed_repository = urlparse(repository_url) if isinstance(repository_url, str) else None
        if not parsed_repository or parsed_repository.scheme != "https" or not parsed_repository.netloc:
            raise ValueError(f"{LAB_DIR / 'page.yaml'}: repository must be an HTTPS URL")
        evidence = evidence_section()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"PROBLEM: {exc}")
        return 1

    hosts = "\n".join(
        "<tr><td>{}</td><td><code>{}</code></td><td><code>{}</code></td></tr>".format(
            html.escape(host["name"]), html.escape(host["ip"]), html.escape(host["ipv6"])
        )
        for host in topology["hosts"]
    )
    answer_blocks_list: list[str] = []
    for key, title in (
        ("network", "My network"),
        ("data_model", "Data model and serialization"),
        ("evidence", "What the evidence shows"),
        ("version_control", "Why Git diff helps"),
    ):
        if key == "evidence":
            points = "\n".join(
                f"<li>{html.escape(point)}</li>" for point in answers["evidence"]
            )
            body = f'<ul class="answer-points">{points}</ul>'
        else:
            body = f"<p>{html.escape(answers[key])}</p>"
        answer_blocks_list.append(f"<section><h2>{title}</h2>{body}</section>")
    answer_blocks = "\n".join(answer_blocks_list)
    repository = html.escape(repository_url, quote=True)
    source_url = html.escape(repository_url.rstrip("/") + "/tree/main/week-02", quote=True)
    diagram = html.escape(mermaid_diagram(topology))
    output = REPO_DIR / "docs" / "week-02" / "index.html"
    document = (
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>WIC2005 Week 2 | Networks as Data</title>
<style>
:root{color-scheme:light;--ink:#172033;--muted:#526071;--accent:#126782;--paper:#fff;--line:#d8e1e8}
*{box-sizing:border-box}body{margin:0;background:#f3f7f9;color:var(--ink);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:auto;padding:28px 20px 60px}header,section{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:24px;margin:18px 0;box-shadow:0 4px 18px #17324a0d}
h1{font-size:clamp(2rem,5vw,3.2rem);margin:.1em 0}h2{color:var(--accent);margin-top:0}.tag{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase}
a{color:var(--accent);font-weight:650}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line)}td code{overflow-wrap:anywhere}
code,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}pre{white-space:pre-wrap;overflow:auto;background:#111827;color:#e7edf4;padding:16px;border-radius:9px}
.missing{color:#9b3d26}details{background:#f8fbfc;border:1px solid var(--line);border-radius:8px;padding:12px;margin:10px 0}summary{cursor:pointer;font-weight:650}.links{columns:2}
.answer-points{padding-left:1.3rem}.answer-points li{margin:.5rem 0}
@media(max-width:640px){main{padding:14px 12px 36px}header,section{padding:18px;margin:12px 0}table{display:block;overflow-x:auto}.links{columns:1}}
</style></head><body><main>
<header><div class="tag">WIC2005 Programmable Networks · matric suffix 4903</div><h1>Week 2: Networks as Data</h1>
<p>A checked topology description builds the Mininet network and supplies this page.</p><p><a href="REPOSITORY">Repository</a> · <a href="SOURCE">Week 2 source and evidence</a></p></header>
<section><h2>Topology</h2><p>A core bridge connects workshop and services access switches in one bridged network.</p><div class="mermaid">DIAGRAM</div></section>
<section><h2>Host addresses</h2><table><thead><tr><th>Host</th><th>IPv4</th><th>IPv6</th></tr></thead><tbody>HOST_ROWS</tbody></table></section>
<section><h2>Every link</h2>LINKS</section>
<section><h2>Experiment evidence</h2><p>These are captured outputs from the running Mininet network.</p>EVIDENCE</section>
ANSWERS
</main><script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script><script>mermaid.initialize({startOnLoad:true,theme:'neutral'});</script></body></html>
""".replace("DIAGRAM", diagram)
        .replace("HOST_ROWS", hosts)
        .replace("LINKS", links_section(topology))
        .replace("EVIDENCE", evidence)
        .replace("ANSWERS", answer_blocks)
        .replace("REPOSITORY", repository)
    )
    document = document.replace("SOURCE", source_url)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(".html.tmp")
    temporary_output.write_text(document, encoding="utf-8")
    temporary_output.replace(output)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
