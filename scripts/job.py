#!/usr/bin/env python3
"""Job folder lifecycle.

  job.py new --lead L-2026-001 --customer "Name" --email a@b.com [--onsite] [--confidential]
  job.py show <job_id>
  job.py set-state <job_id> <state> --by <agent> [--note TEXT]
  job.py list [--state STATE]
"""
import argparse
import sys

from _common import DATA, now, read_json, scan_root, write_json
from ids import next_id

STATES = ["new", "qualified", "quoted", "accepted", "scheduled", "scanned", "processing",
          "qa", "delivered", "invoiced", "paid", "closed", "on_hold", "lost"]

# Who may advance OUT of a state. Mirrors docs/AGENT_PROTOCOL.md section 4.
STATE_OWNER = {
    "new": "intake-coordinator", "qualified": "quote-estimator", "quoted": "owner",
    "accepted": "billing-clerk", "scheduled": "scan-planner", "scanned": "scan-planner",
    "processing": "scan-planner", "qa": "cad-qa", "delivered": "billing-clerk",
    "invoiced": "billing-clerk", "paid": "web-publisher", "closed": "owner",
    "on_hold": "owner", "lost": "owner",
}

ALLOWED = {
    "new": ["qualified", "lost", "on_hold"],
    "qualified": ["quoted", "lost", "on_hold"],
    "quoted": ["accepted", "lost", "on_hold"],
    "accepted": ["scheduled", "on_hold", "lost"],
    "scheduled": ["scanned", "on_hold"],
    "scanned": ["processing", "on_hold"],
    "processing": ["qa", "on_hold"],
    "qa": ["delivered", "processing", "on_hold"],
    "delivered": ["invoiced", "on_hold"],
    "invoiced": ["paid", "on_hold"],
    "paid": ["closed"],
    "closed": [],
    "on_hold": STATES,
    "lost": ["qualified"],
}


def job_dir(job_id):
    return DATA / "jobs" / job_id


def cmd_new(a):
    job_id = next_id("job")
    d = job_dir(job_id)
    (d / "notes").mkdir(parents=True, exist_ok=True)
    job = {
        "job_id": job_id,
        "state": "new",
        "created": now(),
        "updated": now(),
        "confidential": bool(a.confidential),
        "photo_permission": None,
        "lead_id": a.lead,
        "quote_id": None,
        "invoice_id": None,
        "customer": {"id": None, "name": a.customer, "company": a.company,
                     "email": a.email, "phone": a.phone},
        "site": {"type": "onsite" if a.onsite else "shop_dropoff", "address": a.address,
                 "travel_zone": a.zone, "access_notes": None, "onsite_contact": None},
        "scope": {"objects": [], "deliverables": [], "tolerance_mm": None,
                  "units_out": "mm", "coordinate_origin": "TODO — set before quoting",
                  "purpose": a.purpose or "TODO"},
        "schedule": {"scan_date": None, "due_date": None, "rush": False},
        "money": {"quoted": None, "deposit": None, "deposit_paid": False,
                  "invoiced": None, "paid": None},
        "assets_root": f"{scan_root()}/{job_id}",
        "history": [{"ts": now(), "by": "intake-coordinator", "from": None, "to": "new"}],
    }
    write_json(d / "job.json", job)
    write_json(d / "assets.json", {"job_id": job_id, "assets_root": job["assets_root"],
                                   "files": [], "_note": "Tier-1 binaries live on $SCAN_ROOT, never in git."})
    print(job_id)
    print(d / "job.json")
    print(f"Create the working folders on the scan drive:\n  mkdir -p {job['assets_root']}/{{00-raw,10-registered,20-mesh,30-cad,40-delivery,50-renders}}")


def cmd_show(a):
    print(open(job_dir(a.job_id) / "job.json", encoding="utf-8").read())


def cmd_set_state(a):
    path = job_dir(a.job_id) / "job.json"
    job = read_json(path)
    old = job["state"]
    if a.state not in STATES:
        raise SystemExit(f"unknown state {a.state!r}")
    if a.state not in ALLOWED[old]:
        raise SystemExit(f"illegal transition {old} -> {a.state}; allowed: {ALLOWED[old]}")
    owner = STATE_OWNER[old]
    if a.by != owner and a.by != "owner":
        raise SystemExit(
            f"{a.by} may not advance a job out of state {old!r} — that belongs to {owner}. "
            "Stop and report instead of editing out of turn.")
    job["state"] = a.state
    job["updated"] = now()
    job.setdefault("history", []).append(
        {"ts": now(), "by": a.by, "from": old, "to": a.state, "note": a.note})
    write_json(path, job)
    print(f"{a.job_id}: {old} -> {a.state}")


def cmd_list(a):
    rows = []
    for d in sorted((DATA / "jobs").glob("SC-*")):
        f = d / "job.json"
        if not f.exists():
            continue
        j = read_json(f)
        if a.state and j["state"] != a.state:
            continue
        rows.append(j)
    for j in rows:
        print(f"{j['job_id']:<14} {j['state']:<12} {j['customer']['name'][:28]:<30} "
              f"due {j.get('schedule', {}).get('due_date') or '-'}")
    if not rows:
        print("no jobs")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new"); s.set_defaults(fn=cmd_new)
    s.add_argument("--lead"); s.add_argument("--customer", required=True)
    s.add_argument("--company"); s.add_argument("--email", required=True); s.add_argument("--phone")
    s.add_argument("--onsite", action="store_true"); s.add_argument("--address")
    s.add_argument("--zone"); s.add_argument("--purpose"); s.add_argument("--confidential", action="store_true")

    s = sub.add_parser("show"); s.set_defaults(fn=cmd_show); s.add_argument("job_id")

    s = sub.add_parser("set-state"); s.set_defaults(fn=cmd_set_state)
    s.add_argument("job_id"); s.add_argument("state")
    s.add_argument("--by", required=True); s.add_argument("--note")

    s = sub.add_parser("list"); s.set_defaults(fn=cmd_list); s.add_argument("--state")

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
