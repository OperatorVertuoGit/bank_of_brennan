"""Thin shared Airtable REST helper. No dependency beyond requests."""
from __future__ import annotations

import json
import os
import time

import requests

API = "https://api.airtable.com/v0"
RATE_SLEEP = 0.25  # 5 req/sec per base


class AirtableError(RuntimeError):
    pass


class Client:
    def __init__(self, base_id: str | None = None, pat: str | None = None):
        self.base_id = base_id or os.environ["AIRTABLE_BASE_ID"]
        pat = pat or os.environ["AIRTABLE_PAT"]
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {pat}", "Content-Type": "application/json"})

    def _call(self, method: str, url: str, payload=None, params=None, tries: int = 5):
        delay = 2.0
        for _ in range(tries):
            r = self.s.request(
                method, url,
                data=json.dumps(payload) if payload is not None else None,
                params=params,
            )
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2
                continue
            if not r.ok:
                raise AirtableError(f"{method} {url} -> {r.status_code}: {r.text}")
            time.sleep(RATE_SLEEP)
            return r.json()
        raise AirtableError(f"{method} {url} failed after {tries} attempts")

    def list_records(self, table: str, view: str | None = None, fields: list[str] | None = None):
        """Yield every record in a table, following pagination."""
        url = f"{API}/{self.base_id}/{table}"
        params: dict = {"pageSize": 100}
        if view:
            params["view"] = view
        if fields:
            params["fields[]"] = fields
        offset = None
        while True:
            p = dict(params)
            if offset:
                p["offset"] = offset
            data = self._call("GET", url, params=p)
            yield from data.get("records", [])
            offset = data.get("offset")
            if not offset:
                return

    def create_records(self, table: str, records: list[dict], typecast: bool = True):
        """Create records 10 at a time (Airtable's batch limit)."""
        url = f"{API}/{self.base_id}/{table}"
        out = []
        for i in range(0, len(records), 10):
            chunk = records[i:i + 10]
            body = {"records": [{"fields": f} for f in chunk], "typecast": typecast}
            out.extend(self._call("POST", url, body)["records"])
        return out

    def update_records(self, table: str, records: list[dict], typecast: bool = True):
        """records: [{'id': 'rec...', 'fields': {...}}, ...]"""
        url = f"{API}/{self.base_id}/{table}"
        out = []
        for i in range(0, len(records), 10):
            body = {"records": records[i:i + 10], "typecast": typecast}
            out.extend(self._call("PATCH", url, body)["records"])
        return out

    def index_by(self, table: str, key_field: str) -> dict[str, str]:
        """Map a primary/key field value -> record id."""
        return {
            r["fields"].get(key_field): r["id"]
            for r in self.list_records(table, fields=[key_field])
            if r["fields"].get(key_field) is not None
        }
