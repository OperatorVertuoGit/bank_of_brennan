#!/usr/bin/env python3
"""Allocate the next sequential ID. Usage: ids.py next {lead|quote|job|invoice|customer}"""
import sys
from datetime import datetime, timezone

from _common import DATA, read_json, write_json

PREFIX = {"lead": "L", "quote": "Q", "job": "SC", "invoice": "INV", "customer": "C"}


def next_id(kind: str) -> str:
    if kind not in PREFIX:
        raise SystemExit(f"unknown kind {kind!r}; expected one of {sorted(PREFIX)}")
    path = DATA / "registry" / "counters.json"
    counters = read_json(path)
    counters[kind] = counters.get(kind, 0) + 1
    write_json(path, counters)
    n = counters[kind]
    if kind == "customer":
        return f"C-{n:04d}"
    year = datetime.now(timezone.utc).year
    return f"{PREFIX[kind]}-{year}-{n:03d}"


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "next":
        raise SystemExit(__doc__)
    print(next_id(sys.argv[2]))
