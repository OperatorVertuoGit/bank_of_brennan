# Runbook

## Daily pass (5 minutes)

```bash
python3 scripts/bus.py inbox          # what is waiting, for whom
python3 scripts/job.py list           # every job and its state
python3 scripts/bus.py log --limit 20 # what happened yesterday
```

Then, in Claude Code, hand each waiting message to the agent it is addressed to:

> Handle `data/bus/quote-estimator/inbox/<file>.json` using the quote-estimator agent.

Anything flagged `!` needs the owner, not an agent.

## New inquiry, end to end

```bash
# 1. Web form submissions arrive automatically. For a phone call or email:
python3 scripts/bus.py send --from owner --to intake-coordinator \
  --topic lead.received --summary "Voicemail from Ana Ruiz, bronze thru-hull fitting, Dana Point"

# 2. intake-coordinator agent: qualifies, creates the lead + job folder
python3 scripts/job.py new --customer "Dana Point Marine Works" --email ana@example.com \
  --onsite --address "24500 Dana Point Harbor Dr" --zone zone_0 --purpose reverse_engineering
python3 scripts/job.py set-state SC-2026-001 qualified --by intake-coordinator

# 3. quote-estimator agent: prices it, drafts the quote, hands it to you to send
# 4. You send it. On acceptance:
python3 scripts/job.py set-state SC-2026-001 accepted --by owner
python3 scripts/bus.py send --from owner --to billing-clerk --topic quote.accepted \
  --job SC-2026-001 --summary "Accepted Q-2026-001; raise the deposit invoice"

# 5. billing-clerk raises the deposit; on payment it unlocks scheduling
python3 scripts/job.py set-state SC-2026-001 scheduled --by billing-clerk

# 6. scan-planner writes the plan, you go scan, then import:
mkdir -p "$SCAN_ROOT/SC-2026-001"/{00-raw,10-registered,20-mesh,30-cad,40-delivery,50-renders}
cp -R /Volumes/SCANNER/export/* "$SCAN_ROOT/SC-2026-001/00-raw/"
chmod -R a-w "$SCAN_ROOT/SC-2026-001/00-raw"
shasum -a 256 "$SCAN_ROOT/SC-2026-001/00-raw"/*   # into assets.json

# 7. cad-qa gates delivery. 8. billing-clerk invoices. 9. web-publisher drafts the case study.
```

## Weekly

```bash
python3 scripts/validate.py                 # every record still matches its schema
python3 website/build.py                    # site still builds
git add -A && git commit -m "week of $(date +%F)"
git push -u origin main
```

Also weekly: review `data/bus/*/failed/` (nothing should linger there), and check AR with
the billing-clerk agent.

## Backups — the part that actually matters

Tier 0 (this repo) is backed up by pushing to GitHub. Do it weekly at minimum.

Tier 1 (`$SCAN_ROOT`) is the one that will hurt. It is not in git and it is large.

```bash
# nightly, to Tier 2
rsync -av --delete "$SCAN_ROOT/" /Volumes/backup/scan-archive/
# and offsite
rclone sync "$SCAN_ROOT" "$ARCHIVE_URI" --progress
```

Restore-test once a quarter: pick one closed job, restore it from Tier 2 to a scratch
directory, and verify the SHA-256 values in its `assets.json` still match. A backup you
have never restored is not a backup.

## Onboarding a new machine

```bash
git clone <remote> && cd bank_of_brennan
cp ops/.env.example ops/.env    # fill in SCAN_ROOT and the rest
python3 scripts/validate.py     # should print 0 failures
python3 website/build.py        # should print 11 pages
```

No dependencies to install. Standard library only, by design — a shop this size should
not have a broken build because a package moved.
