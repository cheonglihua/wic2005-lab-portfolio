#!/usr/bin/env python3
"""Capture actual CLI rejection output for loop.yaml and missing.yaml."""
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
BUILDER = HERE / "build_routed.py"
OUTPUT = HERE / "evidence3" / "check.txt"

records = []
for label, fixture in (("FORWARDING LOOP", "loop.yaml"), ("MISSING ROUTE", "missing.yaml")):
    result = subprocess.run(
        [sys.executable, str(BUILDER), str(HERE / fixture)],
        cwd=HERE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    records.append(f"== {label}: {fixture} ==\n{result.stdout.rstrip()}\nExit code: {result.returncode}")
    if result.returncode == 0 or "PROBLEM:" not in result.stdout or "nothing was built" not in result.stdout:
        raise SystemExit(f"{fixture} did not produce the expected pre-build rejection")

OUTPUT.write_text("\n\n".join(records) + "\n", encoding="utf-8")
print(f"Captured actual validator output in {OUTPUT}")
