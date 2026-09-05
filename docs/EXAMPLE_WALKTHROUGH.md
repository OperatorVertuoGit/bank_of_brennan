# Worked example — SC-2026-001

One job from web form to paid, showing exactly which file each step touches.
Every command below is real and runnable.

## 1. Visitor submits the quote form

The form provider's webhook pipes the submission in:

```bash
echo '{"name":"Ana Ruiz","company":"Dana Point Marine Works","email":"ana@example.com",
"phone":"949-555-0142","object":"cast bronze thru-hull fitting","size":"180 x 120 x 90 mm",
"purpose":"Reverse engineering","deadline":"2026-09-26",
"location":"It needs to be scanned on site",
"message":"Original is corroded; need a replacement machined."}' \
  | python3 scripts/intake_from_form.py
```

Writes:
- `data/leads/_raw/20260905T152201Z.json` — the untouched submission, kept forever
- `data/bus/intake-coordinator/inbox/20260905T152201Z__webform__lead.received__nojob.json`

## 2. intake-coordinator

```bash
python3 scripts/bus.py inbox intake-coordinator
```

The agent reads the raw submission, checks it against the eight intake facts, allocates
`L-2026-001`, and creates the job folder:

```bash
python3 scripts/job.py new --lead L-2026-001 \
  --customer "Dana Point Marine Works" --email ana@example.com --phone 949-555-0142 \
  --onsite --address "24500 Dana Point Harbor Dr, Dana Point, CA" --zone zone_0 \
  --purpose reverse_engineering
# -> SC-2026-001

python3 scripts/job.py set-state SC-2026-001 qualified --by intake-coordinator \
  --note "8 intake facts captured; tolerance confirmed at 0.5 mm by phone"

python3 scripts/bus.py send --from intake-coordinator --to quote-estimator \
  --topic lead.qualified --job SC-2026-001 \
  --summary "Bronze thru-hull, on-site Dana Point zone_0, RE to STEP, 0.5 mm, due 9/26" \
  --ref data/jobs/SC-2026-001/job.json

python3 scripts/bus.py done data/bus/intake-coordinator/inbox/20260905T152201Z__webform__lead.received__nojob.json
```

The protocol is enforced, not just documented:

```bash
$ python3 scripts/job.py set-state SC-2026-001 delivered --by cad-qa
illegal transition new -> delivered; allowed: ['qualified', 'lost', 'on_hold']

$ python3 scripts/job.py set-state SC-2026-001 qualified --by cad-qa
cad-qa may not advance a job out of state 'new' — that belongs to intake-coordinator.
Stop and report instead of editing out of turn.
```

## 3. quote-estimator

Reads `pricing.json`, `equipment.json`, `service-area.json`. Zone 0 → no travel line.
Writes `data/quotes/Q-2026-001.json` + `.md`, advances to `quoted`, messages the **owner**
(not the client) with `quote.drafted`.

## 4. Owner sends it. Client accepts.

```bash
python3 scripts/job.py set-state SC-2026-001 accepted --by owner
python3 scripts/bus.py send --from owner --to billing-clerk --topic quote.accepted \
  --job SC-2026-001 --summary "Accepted Q-2026-001 — raise the 50% deposit"
```

## 5. billing-clerk → scan-planner

Deposit invoice `INV-2026-001` staged, owner sends, payment clears:

```bash
python3 scripts/job.py set-state SC-2026-001 scheduled --by billing-clerk
python3 scripts/bus.py send --from billing-clerk --to scan-planner --topic deposit.paid \
  --job SC-2026-001 --summary "Deposit cleared; scheduling unlocked"
```

## 6. scan-planner

Writes `data/jobs/SC-2026-001/scan-plan.json` — handheld laser (0.10 mm/m volumetric vs.
0.5 mm contracted, comfortable margin), matting spray with written permission, datum at
the flange face, tide window checked with the yard.

After the visit:

```bash
mkdir -p "$SCAN_ROOT/SC-2026-001"/{00-raw,10-registered,20-mesh,30-cad,40-delivery,50-renders}
cp -R /Volumes/SCANNER/export/* "$SCAN_ROOT/SC-2026-001/00-raw/"
chmod -R a-w "$SCAN_ROOT/SC-2026-001/00-raw"
shasum -a 256 "$SCAN_ROOT/SC-2026-001/00-raw"/*   # -> assets.json
```

`00-raw/` is read-only from here on. Everything downstream re-derives from it.

## 7. cad-qa gates delivery

Fails the job back if units are wrong, the origin is not the flange face, deviation
exceeds 0.5 mm, the STEP will not import as a closed solid, or a contracted format is
missing. On pass it writes `qa-report.json` and `delivery-note.md` — the delivery note
names every surface reconstructed by inference, which for a corroded original is most of
the sealing face.

## 8. Deliver, invoice, publish

```bash
python3 scripts/job.py set-state SC-2026-001 invoiced --by billing-clerk
python3 scripts/job.py set-state SC-2026-001 paid --by billing-clerk
python3 scripts/bus.py send --from billing-clerk --to web-publisher --topic invoice.paid \
  --job SC-2026-001 --summary "Paid. Portfolio candidate — client gave photo permission."
python3 scripts/job.py set-state SC-2026-001 closed --by web-publisher
```

## 9. The whole history, any time

```bash
python3 scripts/bus.py log --job SC-2026-001
```
