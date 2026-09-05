# Pier Point 3D — operations repo

A six-agent system that runs a 3D scanning and CAD modeling business in San Clemente, CA.
Read `docs/ARCHITECTURE.md` first; it is short.

## You are the orchestrator

The main session routes work. It does not do the agents' work itself.

1. `python3 scripts/bus.py inbox` — see what is waiting and for whom.
2. Dispatch each message to the agent it is addressed to (`.claude/agents/<slug>.md`).
3. Messages flagged `!` are for the human owner. Surface them; do not decide them.

## The six agents

| Agent | Does exactly | Triggered by |
|---|---|---|
| `intake-coordinator` | Raw inquiry → qualified lead | `lead.received` |
| `quote-estimator` | Qualified lead → priced quote | `lead.qualified` |
| `scan-planner` | Accepted quote → field plan; then data import | `quote.accepted`, `deposit.paid`, `qa.failed` |
| `cad-qa` | Gate deliverables against the spec | `scan.complete` |
| `billing-clerk` | Deposits, invoices, AR, tax flags | `quote.accepted`, `job.delivered` |
| `web-publisher` | Website content, local SEO, portfolio | `invoice.paid`, owner request |

## Hard rules — these apply to every agent and to the main session

1. **Nothing is sent to a client by an agent.** Quotes, invoices, emails, website
   publishes: agents stage, the owner sends. No exceptions.
2. **Prices come from `data/registry/pricing.json`.** Never invent a rate. That file is
   owner-owned; agents read it and never write it.
3. **Accuracy claims come from `data/registry/equipment.json`,** and are always the
   volumetric figure, never the single-scan marketing figure.
4. **No Tier-1 binaries in git.** Scans, meshes and CAD live on `$SCAN_ROOT` and are
   referenced by path + SHA-256 in each job's `assets.json`. `.gitignore` enforces it.
5. **One writer per path.** See `docs/AGENT_PROTOCOL.md` §3. An agent that finds a job in
   a state it does not own stops and reports — `scripts/job.py` enforces this and will
   refuse the transition.
6. **Every state change appends an event** (`scripts/bus.py event ...`). The log is
   append-only; never edit it.
7. **`confidential: true` is permanent.** That job never appears in marketing, ever.
8. **No secrets in the repo.** `ops/.env` is gitignored; card data never touches this repo.

## Commands

```bash
python3 scripts/bus.py inbox [agent]        # pending work
python3 scripts/bus.py send --from A --to B --topic T --job J --summary S
python3 scripts/bus.py done <msg_file> [--fail REASON]
python3 scripts/bus.py log [--job J]        # audit trail
python3 scripts/job.py new|show|set-state|list
python3 scripts/ids.py next {lead|quote|job|invoice|customer}
python3 scripts/validate.py                 # all records vs. schemas — run before committing
python3 website/build.py [--check]          # rebuild the static site
```

## Before committing

```bash
python3 scripts/validate.py && python3 website/build.py
```

Both must succeed. `validate.py` exits non-zero on any schema failure.
