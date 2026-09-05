# Agent protocol

Rules every agent follows. Violations are bugs.

## 1. Message envelope

Every bus message is one JSON file: `data/bus/<to>/inbox/<msg_id>.json`
`msg_id` = `<UTC ISO compact>__<from>__<topic>__<job_id>` e.g.
`20260905T183000Z__quote-estimator__quote.accepted__SC-2026-001.json`

```json
{
  "msg_id":   "20260905T183000Z__quote-estimator__quote.accepted__SC-2026-001",
  "ts":       "2026-09-05T18:30:00Z",
  "from":     "quote-estimator",
  "to":       "scan-planner",
  "topic":    "quote.accepted",
  "job_id":   "SC-2026-001",
  "refs":     ["data/quotes/Q-2026-001.json"],
  "summary":  "Client accepted Q-2026-001. Boat hull scan, Dana Point Harbor, needs on-site.",
  "requires_human": false,
  "due":      "2026-09-09"
}
```

Rules:
- Messages **point**, they do not carry. Put facts in the job folder; reference them in `refs`.
- `summary` is one or two sentences a human can act on without opening anything else.
- Never write into another agent's `processed/` or `failed/`.
- Processing a message: do the work → append event → `git mv` the message to `processed/`.
- Cannot do the work: add `"error"` and `"blocked_on"` fields → move to `failed/` → also
  write a `needs.human` message to `ops/INBOX_OWNER.md`.

## 2. Topics (the complete list)

| Topic | From | To | Fires when |
|---|---|---|---|
| `lead.received` | web form / email relay | intake-coordinator | Public form submitted |
| `lead.qualified` | intake-coordinator | quote-estimator | Lead has scope, budget signal, contact |
| `lead.disqualified` | intake-coordinator | — (event only) | Out of area, out of scope, spam |
| `quote.drafted` | quote-estimator | owner | Quote ready for human send |
| `quote.accepted` | owner / intake | scan-planner + billing-clerk | Client signs |
| `quote.declined` | intake-coordinator | — (event only) | Client passes |
| `deposit.paid` | billing-clerk | scan-planner | Deposit cleared; scheduling unlocked |
| `scan.scheduled` | scan-planner | owner | Date + plan confirmed |
| `scan.complete` | scan-planner | cad-qa | Raw data imported + checksummed |
| `qa.passed` | cad-qa | billing-clerk | Deliverables meet spec |
| `qa.failed` | cad-qa | scan-planner | Rework needed; reasons enumerated |
| `job.delivered` | owner | billing-clerk | Client has the files |
| `invoice.sent` | billing-clerk | — (event only) | Final invoice issued |
| `invoice.paid` | billing-clerk | web-publisher | Paid; portfolio candidate |
| `portfolio.drafted` | web-publisher | owner | Case study ready for approval |
| `needs.human` | any | owner | Blocked on a decision only the owner can make |

## 3. Write scopes — one writer per path

| Path | Sole writer |
|---|---|
| `data/leads/**` | intake-coordinator |
| `data/quotes/**` | quote-estimator |
| `data/jobs/<id>/job.json` | whichever agent owns the current state (see §4) |
| `data/jobs/<id>/scan-plan.json`, `field-report.md` | scan-planner |
| `data/jobs/<id>/qa-report.json` | cad-qa |
| `data/jobs/<id>/assets.json` | scan-planner (import), cad-qa (delivery) |
| `data/invoices/**` | billing-clerk |
| `website/content/**`, `website/theme/**` | web-publisher |
| `data/registry/pricing.json` | **owner only** — agents read, never write |
| `data/bus/events/*.jsonl` | all agents, append-only |

Everyone may read everything except `ops/.env`.

## 4. State ownership

| Job state | Owner agent | May advance to |
|---|---|---|
| `new` | intake-coordinator | `qualified`, `lost` |
| `qualified` | quote-estimator | `quoted` |
| `quoted` | owner | `accepted`, `lost`, `on_hold` |
| `accepted` | billing-clerk | `scheduled` (after deposit) |
| `scheduled` | scan-planner | `scanned` |
| `scanned` | scan-planner | `processing` |
| `processing` | scan-planner | `qa` |
| `qa` | cad-qa | `delivered` (pass) or back to `processing` (fail) |
| `delivered` | billing-clerk | `invoiced` |
| `invoiced` | billing-clerk | `paid` |
| `paid` | web-publisher | `closed` |

An agent that finds a job in a state it does not own **stops and reports** — it never
edits out of turn.

## 5. Event record

Appended to `data/bus/events/YYYY-MM.jsonl`, one line each:

```json
{"ts":"2026-09-05T18:30:00Z","actor":"cad-qa","event":"qa.failed","job_id":"SC-2026-001","detail":"Hull mesh non-manifold at 3 locations; tolerance 0.9mm exceeds 0.5mm spec","refs":["data/jobs/SC-2026-001/qa-report.json"]}
```

Append with `scripts/bus.py event ...` — never hand-edit the log.

## 6. Non-negotiables for every agent

1. **Never invent a price.** Read `data/registry/pricing.json`. If a line item is not in
   it, escalate `needs.human`.
2. **Never promise a tolerance the equipment cannot hold.** Accuracy claims come from
   `data/registry/equipment.json`, per-device, and quote the *volumetric* figure for
   large parts, not the single-scan figure.
3. **Never commit Tier-1 binaries.** Reference by path + SHA-256 in `assets.json`.
4. **Never send anything externally** — email, invoice, quote, website publish. Agents
   stage; the owner sends.
5. **Never store a client's proprietary geometry outside `$SCAN_ROOT`,** and honor any
   NDA flag on the job (`job.json:confidential = true` blocks portfolio use forever).
6. **Always append an event** for anything that changes state.
