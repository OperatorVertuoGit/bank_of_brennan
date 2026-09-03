#!/usr/bin/env python3
"""Load schema/seed_data.json into the Layers and Feature Codes tables.

Idempotent: existing rows are updated in place, matched on their primary field.

    export AIRTABLE_PAT=pat... AIRTABLE_BASE_ID=app...
    python scripts/seed_reference_data.py
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _airtable import Client  # noqa: E402

SEED = pathlib.Path(__file__).resolve().parents[1] / "schema" / "seed_data.json"


def upsert(c: Client, table: str, key: str, rows: list[dict]) -> dict[str, str]:
    existing = c.index_by(table, key)
    creates = [r for r in rows if r[key] not in existing]
    updates = [{"id": existing[r[key]], "fields": r} for r in rows if r[key] in existing]
    if creates:
        c.create_records(table, creates)
    if updates:
        c.update_records(table, updates)
    print(f"{table}: {len(creates)} created, {len(updates)} updated")
    return c.index_by(table, key)


def main() -> int:
    seed = json.loads(SEED.read_text())
    c = Client()

    layer_ids = upsert(c, "Layers", "Layer ID", seed["Layers"])

    codes = []
    for row in seed["Feature Codes"]:
        row = dict(row)
        slug = row.pop("Layer", None)
        if slug:
            rec = layer_ids.get(slug)
            if not rec:
                print(f"  ! code {row['Code']}: layer {slug} missing, link skipped")
            else:
                row["Layer"] = [rec]
        codes.append(row)
    upsert(c, "Feature Codes", "Code", codes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
