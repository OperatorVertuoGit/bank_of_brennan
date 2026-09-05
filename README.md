# bank_of_brennan — Pier Point 3D operations system

A complete, file-based operating system for a small 3D scanning and CAD modeling
business in San Clemente, California: six specialized agents, a filesystem message bus,
a schema-validated record store, and a static marketing website.

No database, no queue broker, no SaaS. Standard-library Python only.

```
.claude/agents/     six agent definitions
docs/               architecture, agent protocol, data model, website, runbook
data/
  registry/         rate card, equipment specs, service-area zones, counters  (owner-owned)
  schemas/          JSON Schema for every record type
  templates/        quote, invoice, delivery note, scan plan
  leads/ quotes/ jobs/ invoices/     the record store
  bus/              per-agent inbox/processed/failed + append-only event log
scripts/            bus.py, job.py, ids.py, validate.py, intake_from_form.py
website/            content JSON → build.py → static site
ops/                .env.example, owner decision inbox
```

## The team

| Agent | One job |
|---|---|
| `intake-coordinator` | Raw inquiry → validated, qualified lead |
| `quote-estimator` | Qualified lead → itemized quote from the rate card |
| `scan-planner` | Accepted quote → field-ready scan plan; data import and checksums |
| `cad-qa` | Gate every deliverable against the contracted spec |
| `billing-clerk` | Deposits, invoices, AR, California tax flags |
| `web-publisher` | Website content, local SEO, portfolio case studies |

## How they talk

- **Job folder** (`data/jobs/<id>/`) — shared state, one writer per file.
- **Bus** (`data/bus/<agent>/inbox/*.json`) — directed handoffs that point, never carry.
- **Event log** (`data/bus/events/YYYY-MM.jsonl`) — append-only audit trail.

Full protocol, including the complete topic list and write scopes:
[`docs/AGENT_PROTOCOL.md`](docs/AGENT_PROTOCOL.md).

## Where data lives

| Tier | Contents | Location |
|---|---|---|
| 0 | Records, docs, website source | this git repo |
| 1 | Raw scans, meshes, CAD (GB/job) | `$SCAN_ROOT` — NAS or external SSD |
| 2 | Archive + client delivery | cloud bucket (`$ARCHIVE_URI`) |
| 3 | Secrets | `ops/.env`, gitignored |

Tier 1 never enters git. Job records point at it by path + SHA-256.

## Quick start

```bash
cp ops/.env.example ops/.env      # set SCAN_ROOT
python3 scripts/validate.py       # 0 failures
python3 website/build.py          # 11 pages -> website/public
python3 scripts/bus.py inbox      # empty
```

Then set the real values in `data/registry/pricing.json`,
`data/registry/equipment.json` and `website/content/site.json` — every number in them
ships as a clearly marked placeholder.

Day-to-day: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).
