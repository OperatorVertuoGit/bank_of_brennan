# Architecture — Pier Point 3D operations system

A six-agent team that runs a 3D scanning + CAD modeling shop in San Clemente, CA.
Everything is plain files. No database server, no queue broker, no SaaS lock-in.

## 1. The team

| # | Agent | Slug | Owns exactly one thing |
|---|-------|------|------------------------|
| 1 | Intake Coordinator | `intake-coordinator` | Turn a raw inquiry into a validated, qualified `lead` record |
| 2 | Quote Estimator | `quote-estimator` | Turn a qualified lead into a priced `quote` |
| 3 | Scan Planner | `scan-planner` | Turn an accepted quote into a field-ready `scan plan` |
| 4 | CAD Deliverable QA | `cad-qa` | Verify deliverables against the job spec before anything ships |
| 5 | Billing Clerk | `billing-clerk` | Deposits, invoices, payment state, CA tax flags |
| 6 | Web Publisher | `web-publisher` | Website content, service pages, local SEO, portfolio entries |

The human owner is the only approver for: sending a quote, going on site,
delivering files, and publishing the website. Agents prepare; the owner presses send.

There is no 7th "manager" agent. The main Claude session is the orchestrator and
routes work by reading `data/bus/*/inbox/`.

## 2. How they communicate

Three mechanisms, in order of importance.

### 2a. The job folder — shared state (pull)
`data/jobs/SC-2026-001/` is the single source of truth for one engagement.
Any agent may **read** any file in it. Each agent may **write** only the files it owns
(see `docs/AGENT_PROTOCOL.md` §Write scopes). One writer per path = no merge conflicts.

### 2b. The bus — directed handoff (push)
`data/bus/<agent-slug>/inbox/<msg_id>.json`

An agent finishing its step writes a message into the *next* agent's inbox.
The receiving agent processes it and moves the file to `processed/` (or `failed/`
with an `error` field). Messages are small: they point at a job, they never carry payload.

```
intake-coordinator ──lead.qualified──▶ quote-estimator
quote-estimator    ──quote.accepted──▶ scan-planner ──▶ billing-clerk (deposit)
scan-planner       ──scan.complete───▶ cad-qa
cad-qa             ──qa.passed───────▶ billing-clerk ──▶ web-publisher (portfolio)
any agent          ──needs.human─────▶ owner (ops/INBOX_OWNER.md)
```

### 2c. The event log — append-only audit (broadcast)
`data/bus/events/YYYY-MM.jsonl` — one JSON object per line, never edited, never deleted.
Every agent appends one event per meaningful action. This is the audit trail, the
"what happened to job SC-2026-014" history, and the source for monthly metrics.

Nothing is deleted in this system. State moves; history accumulates.

## 3. Where data is held — four tiers

| Tier | What | Where | Versioned | Backup |
|------|------|-------|-----------|--------|
| **0 — Records** | Leads, quotes, jobs, invoices, events, website source | This git repo | Git history | GitHub remote |
| **1 — Working scan data** | Raw scans, point clouds, meshes, CAD, renders (GB per job) | `$SCAN_ROOT` — local NAS / external SSD | No (checksummed) | Nightly rsync to Tier 2 |
| **2 — Archive + client delivery** | Delivered packages, cold storage after 30 days | Cloud bucket / Google Drive (`$ARCHIVE_URI`) | No | Provider-side |
| **3 — Secrets** | API keys, Stripe keys, form webhook secret | `ops/.env` (gitignored) + password manager | Never | Password manager |

**Tier 1 never enters git.** A job folder in Tier 0 holds an `assets.json` that
*points* at Tier 1/2 paths with sizes and SHA-256 checksums. Text records are tiny
and diffable; binaries stay out of history.

```
$SCAN_ROOT/SC-2026-001/
  00-raw/         # scanner exports, untouched, read-only after import
  10-registered/  # aligned/registered point clouds
  20-mesh/        # cleaned, decimated meshes
  30-cad/         # parametric CAD, native + STEP
  40-delivery/    # exactly what the client receives
  50-renders/     # marketing stills (feeds web-publisher portfolio)
```

`00-raw/` is set read-only on import. If a job is ever re-cut, it re-cuts from raw.

## 4. Website

Static site, no runtime, no database. Content lives in JSON; a ~200-line
dependency-free Python generator renders `website/public/`. See `docs/WEBSITE.md`.

Deploy target: Cloudflare Pages or Netlify pointed at `website/public/`.
Quote form posts to a form endpoint whose webhook drops JSON into
`data/bus/intake-coordinator/inbox/` — that is the seam between the public
website and the internal agent system.

## 5. Job lifecycle

```
new ─▶ qualified ─▶ quoted ─▶ accepted ─▶ scheduled ─▶ scanned
    ─▶ processing ─▶ qa ─▶ delivered ─▶ invoiced ─▶ paid ─▶ closed
```
Off-ramps from any state: `on_hold`, `lost`.
Only the agent that owns a state may advance out of it (`docs/AGENT_PROTOCOL.md`).
