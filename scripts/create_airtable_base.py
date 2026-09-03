#!/usr/bin/env python3
"""Build the Henderson tilt-up survey base in Airtable from schema/airtable_schema.json.

Airtable's Metadata API cannot create formula, rollup, lookup, or count fields. Those are
printed as a manual checklist at the end with the exact expression to paste.

Usage:
    export AIRTABLE_PAT=pat...          # needs schema.bases:write (+ schema.bases:read)
    export AIRTABLE_WORKSPACE_ID=wsp... # only when creating a new base
    python scripts/create_airtable_base.py --name "Henderson Tilt-Up Survey"
    python scripts/create_airtable_base.py --base-id appXXXX      # add to an existing base
    python scripts/create_airtable_base.py --base-id appXXXX --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

import requests

API = "https://api.airtable.com/v0/meta"
SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "schema" / "airtable_schema.json"
RATE_SLEEP = 0.25  # Airtable allows 5 req/sec per base

SELECT_PALETTE = [
    "blueLight2", "cyanLight2", "tealLight2", "greenLight2", "yellowLight2",
    "orangeLight2", "redLight2", "pinkLight2", "purpleLight2", "grayLight2",
]


class AirtableError(RuntimeError):
    pass


def session(pat: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {pat}", "Content-Type": "application/json"})
    return s


def call(s: requests.Session, method: str, url: str, payload=None, tries: int = 5):
    """One Airtable request with backoff on 429 and 5xx."""
    delay = 2.0
    for attempt in range(tries):
        r = s.request(method, url, data=json.dumps(payload) if payload is not None else None)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(delay)
            delay *= 2
            continue
        if not r.ok:
            raise AirtableError(f"{method} {url} -> {r.status_code}: {r.text}")
        time.sleep(RATE_SLEEP)
        return r.json()
    raise AirtableError(f"{method} {url} failed after {tries} attempts")


def field_payload(f: dict) -> dict | None:
    """Translate a schema field into an Airtable Metadata API field object.

    Returns None for field types the API cannot create.
    """
    if f.get("apiCreatable") is False:
        return None

    ftype = f["type"]
    out: dict = {"name": f["name"], "type": ftype}
    if f.get("note"):
        out["description"] = f["note"][:1000]

    if ftype == "number":
        out["options"] = {"precision": f.get("options", {}).get("precision", 2)}
    elif ftype == "singleSelect":
        choices = f["options"]["choices"]
        out["options"] = {
            "choices": [
                {"name": c, "color": SELECT_PALETTE[i % len(SELECT_PALETTE)]}
                for i, c in enumerate(choices)
            ]
        }
    elif ftype == "date":
        out["options"] = {"dateFormat": {"name": "iso"}}
    elif ftype == "checkbox":
        out["options"] = {"icon": "check", "color": "greenBright"}
    elif ftype == "multipleRecordLinks":
        # linkedTableId is filled in during the second pass
        return None
    elif ftype in ("singleLineText", "multilineText", "multipleAttachments"):
        pass
    else:
        raise AirtableError(f"unhandled field type {ftype!r} on {f['name']!r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-id", help="existing base to add tables to")
    ap.add_argument("--name", default="Henderson Tilt-Up Survey", help="name for a new base")
    ap.add_argument("--workspace-id", default=os.environ.get("AIRTABLE_WORKSPACE_ID"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pat = os.environ.get("AIRTABLE_PAT")
    if not pat and not args.dry_run:
        print("AIRTABLE_PAT is not set", file=sys.stderr)
        return 2

    schema = json.loads(SCHEMA_PATH.read_text())
    tables = {t["name"]: t for t in schema["tables"]}
    order = schema["creationOrder"]

    if args.dry_run:
        for name in order:
            t = tables[name]
            direct = [f for f in t["fields"] if field_payload(f)]
            links = [f for f in t["fields"] if f["type"] == "multipleRecordLinks"]
            manual = [f for f in t["fields"] if f.get("apiCreatable") is False]
            print(f"{name:20s} direct={len(direct):3d} links={len(links):3d} manual={len(manual):3d}")
        return 0

    s = session(pat)

    # --- base ---------------------------------------------------------------
    if args.base_id:
        base_id = args.base_id
        existing = {t["name"]: t["id"] for t in call(s, "GET", f"{API}/bases/{base_id}/tables")["tables"]}
        print(f"using base {base_id} ({len(existing)} existing tables)")
    else:
        if not args.workspace_id:
            print("--workspace-id or AIRTABLE_WORKSPACE_ID required to create a base", file=sys.stderr)
            return 2
        first = tables[order[0]]
        body = {
            "name": args.name,
            "workspaceId": args.workspace_id,
            "tables": [{
                "name": first["name"],
                "description": first.get("description", "")[:20000],
                "fields": [p for p in (field_payload(f) for f in first["fields"]) if p],
            }],
        }
        created = call(s, "POST", f"{API}/bases", body)
        base_id = created["id"]
        existing = {t["name"]: t["id"] for t in created["tables"]}
        print(f"created base {base_id}")

    # --- pass 1: tables with their non-link fields ---------------------------
    table_ids: dict[str, str] = dict(existing)
    for name in order:
        if name in table_ids:
            print(f"  = {name} (exists)")
            continue
        t = tables[name]
        body = {
            "name": name,
            "description": t.get("description", "")[:20000],
            "fields": [p for p in (field_payload(f) for f in t["fields"]) if p],
        }
        res = call(s, "POST", f"{API}/bases/{base_id}/tables", body)
        table_ids[name] = res["id"]
        print(f"  + {name} ({len(body['fields'])} fields)")

    # --- pass 2: linked-record fields ---------------------------------------
    print("\nlinking tables")
    live = call(s, "GET", f"{API}/bases/{base_id}/tables")["tables"]
    existing_fields = {t["id"]: {fl["name"] for fl in t["fields"]} for t in live}
    for name in order:
        t = tables[name]
        tid = table_ids[name]
        have = existing_fields.get(tid, set())
        for f in t["fields"]:
            if f["type"] != "multipleRecordLinks" or f["name"] in have:
                continue
            linked = table_ids.get(f["linkedTable"])
            if not linked:
                print(f"  ! {name}.{f['name']} -> {f['linkedTable']} not found, skipped")
                continue
            body = {
                "name": f["name"],
                "type": "multipleRecordLinks",
                "options": {"linkedTableId": linked, "prefersSingleRecordLink": False},
            }
            try:
                call(s, "POST", f"{API}/bases/{base_id}/tables/{tid}/fields", body)
                print(f"  + {name}.{f['name']} -> {f['linkedTable']}")
            except AirtableError as e:
                print(f"  ! {name}.{f['name']}: {e}")

    # --- manual checklist ----------------------------------------------------
    print("\n" + "=" * 78)
    print("MANUAL FIELDS -- the Metadata API cannot create these. Add them in the UI.")
    print("=" * 78)
    for name in order:
        manual = [f for f in tables[name]["fields"] if f.get("apiCreatable") is False]
        if not manual:
            continue
        print(f"\n{name}")
        for f in manual:
            print(f"  [ ] {f['name']}  ({f['type']})")
            print(f"        {f.get('manual', '')}")

    print(f"\nbase: https://airtable.com/{base_id}")
    print("Airtable auto-creates the reverse link field on the other side of each link;")
    print("rename those to something readable before the base gets busy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
