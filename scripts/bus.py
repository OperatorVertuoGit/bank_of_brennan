#!/usr/bin/env python3
"""The message bus and event log.

  bus.py send --from A --to B --topic T --job J --summary S [--ref PATH ...] [--human]
  bus.py inbox [agent]                 list pending messages
  bus.py done <msg_file> [--fail REASON]
  bus.py event --actor A --event E [--job J] [--detail D] [--ref PATH ...]
  bus.py log [--job J] [--limit N]
"""
import argparse
import pathlib
import shutil

from _common import AGENTS, BUS, now, read_json, stamp, write_json

TOPICS = [
    "lead.received", "lead.qualified", "lead.disqualified", "quote.drafted",
    "quote.accepted", "quote.declined", "deposit.paid", "scan.scheduled",
    "scan.complete", "qa.passed", "qa.failed", "job.delivered", "invoice.sent",
    "invoice.paid", "portfolio.drafted", "needs.human",
]


def cmd_send(a):
    if a.topic not in TOPICS:
        raise SystemExit(f"unknown topic {a.topic!r}; expected one of {TOPICS}")
    if a.to not in AGENTS and a.to != "owner":
        raise SystemExit(f"unknown recipient {a.to!r}")
    msg_id = f"{stamp()}__{getattr(a, 'from')}__{a.topic}__{a.job or 'nojob'}"
    msg = {
        "msg_id": msg_id,
        "ts": now(),
        "from": getattr(a, "from"),
        "to": a.to,
        "topic": a.topic,
        "job_id": a.job,
        "refs": a.ref or [],
        "summary": a.summary,
        "requires_human": bool(a.human) or a.to == "owner",
        "due": a.due,
    }
    dest = BUS / a.to / "inbox" / f"{msg_id}.json"
    write_json(dest, msg)
    _append_event({"ts": now(), "actor": getattr(a, "from"), "event": f"msg.sent:{a.topic}",
                   "job_id": a.job, "detail": a.summary, "refs": [str(dest.relative_to(BUS.parent.parent))]})
    print(dest)


def cmd_inbox(a):
    targets = [a.agent] if a.agent else AGENTS + ["owner"]
    found = 0
    for agent in targets:
        inbox = BUS / agent / "inbox"
        if not inbox.exists():
            continue
        for f in sorted(inbox.glob("*.json")):
            m = read_json(f)
            flag = "!" if m.get("requires_human") else " "
            print(f"{flag} {agent:<20} {m['topic']:<20} {m.get('job_id') or '-':<12} {m['summary'][:70]}")
            print(f"    {f}")
            found += 1
    if not found:
        print("inbox empty")


def cmd_done(a):
    src = pathlib.Path(a.msg_file)
    if not src.exists():
        raise SystemExit(f"no such message: {src}")
    msg = read_json(src)
    bucket = "failed" if a.fail else "processed"
    if a.fail:
        msg["error"] = a.fail
        msg["failed_at"] = now()
        write_json(src, msg)
    dest = src.parent.parent / bucket / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    _append_event({"ts": now(), "actor": msg.get("to", "unknown"),
                   "event": f"msg.{bucket}:{msg.get('topic')}", "job_id": msg.get("job_id"),
                   "detail": a.fail or msg.get("summary"), "refs": []})
    print(dest)


def _append_event(ev):
    month = ev["ts"][:7]
    path = BUS / "events" / f"{month}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    import json as _json
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(ev, ensure_ascii=False) + "\n")
    return path


def cmd_event(a):
    print(_append_event({"ts": now(), "actor": a.actor, "event": a.event,
                         "job_id": a.job, "detail": a.detail, "refs": a.ref or []}))


def cmd_log(a):
    import json as _json
    rows = []
    for f in sorted((BUS / "events").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = _json.loads(line)
            if a.job and ev.get("job_id") != a.job:
                continue
            rows.append(ev)
    for ev in rows[-a.limit:]:
        print(f"{ev['ts']}  {ev['actor']:<20} {ev['event']:<28} {ev.get('job_id') or '-':<12} {ev.get('detail') or ''}")
    if not rows:
        print("no events")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("send"); s.set_defaults(fn=cmd_send)
    s.add_argument("--from", required=True, dest="from")
    s.add_argument("--to", required=True)
    s.add_argument("--topic", required=True)
    s.add_argument("--job")
    s.add_argument("--summary", required=True)
    s.add_argument("--ref", action="append")
    s.add_argument("--due")
    s.add_argument("--human", action="store_true")

    s = sub.add_parser("inbox"); s.set_defaults(fn=cmd_inbox); s.add_argument("agent", nargs="?")

    s = sub.add_parser("done"); s.set_defaults(fn=cmd_done)
    s.add_argument("msg_file"); s.add_argument("--fail")

    s = sub.add_parser("event"); s.set_defaults(fn=cmd_event)
    s.add_argument("--actor", required=True); s.add_argument("--event", required=True)
    s.add_argument("--job"); s.add_argument("--detail"); s.add_argument("--ref", action="append")

    s = sub.add_parser("log"); s.set_defaults(fn=cmd_log)
    s.add_argument("--job"); s.add_argument("--limit", type=int, default=40)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
