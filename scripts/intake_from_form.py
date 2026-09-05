#!/usr/bin/env python3
"""Website quote form -> intake-coordinator inbox.

The public form posts to the endpoint in website/content/site.json. That provider's
webhook (or a scheduled poll) pipes the JSON body into this script:

    curl -s "$FORM_PROVIDER_EXPORT" | python3 scripts/intake_from_form.py
    python3 scripts/intake_from_form.py < submission.json

It writes a raw copy under data/leads/_raw/ and a lead.received message into
data/bus/intake-coordinator/inbox/. It deliberately does NOT create a lead record —
that is the intake-coordinator's job, and it involves judgment.
"""
import json
import sys

from _common import BUS, DATA, now, stamp, write_json

FIELDS = ["name", "company", "email", "phone", "object", "size", "purpose",
          "deadline", "location", "message", "files"]


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"stdin is not JSON: {e}")

    submissions = payload if isinstance(payload, list) else [payload]
    for sub in submissions:
        sid = stamp()
        raw_path = write_json(DATA / "leads" / "_raw" / f"{sid}.json", sub)
        who = sub.get("name") or sub.get("email") or "unknown"
        what = (sub.get("object") or sub.get("message") or "")[:100]
        msg_id = f"{sid}__webform__lead.received__nojob"
        write_json(BUS / "intake-coordinator" / "inbox" / f"{msg_id}.json", {
            "msg_id": msg_id,
            "ts": now(),
            "from": "webform",
            "to": "intake-coordinator",
            "topic": "lead.received",
            "job_id": None,
            "refs": [str(raw_path.relative_to(DATA.parent))],
            "summary": f"Web form submission from {who}: {what}",
            "requires_human": False,
            "due": None,
        })
        print(f"queued {msg_id}")


if __name__ == "__main__":
    main()
