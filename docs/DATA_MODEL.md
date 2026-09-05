# Data model

IDs
- Lead:    `L-YYYY-NNN`
- Quote:   `Q-YYYY-NNN`
- Job:     `SC-YYYY-NNN`   (SC = San Clemente)
- Invoice: `INV-YYYY-NNN`
Counters live in `data/registry/counters.json`; allocate with `scripts/ids.py next <kind>`.

All timestamps are UTC ISO-8601 with `Z`. All money is USD, stored as a number of
dollars with 2 decimals. All lengths are millimeters unless the field name ends `_in`.

## Files on disk

```
data/
  registry/
    pricing.json       # rate card — OWNER WRITES ONLY
    equipment.json     # scanners, accuracy envelopes, day rates
    service-area.json  # travel zones from San Clemente
    counters.json      # ID sequences
    customers.json     # customer directory (dedupe key = email)
  leads/L-2026-001.json
  quotes/Q-2026-001.json
  invoices/INV-2026-001.json
  jobs/SC-2026-001/
    job.json           # spine: state, customer, scope, links
    scan-plan.json     # scan-planner
    field-report.md    # scan-planner, written on site
    assets.json        # pointers into $SCAN_ROOT + checksums
    qa-report.json     # cad-qa
    delivery-note.md   # what shipped, formats, units, coordinate origin
    notes/             # freeform, dated markdown
  bus/
    events/2026-09.jsonl
    <agent>/inbox|processed|failed/
```

## job.json (the spine)

```json
{
  "job_id": "SC-2026-001",
  "state": "scheduled",
  "created": "2026-09-05T18:00:00Z",
  "updated": "2026-09-08T15:12:00Z",
  "customer": { "id": "C-0007", "name": "Dana Point Marine Works", "contact": "Ana Ruiz",
                "email": "ana@example.com", "phone": "+1-949-555-0142" },
  "lead_id": "L-2026-001",
  "quote_id": "Q-2026-001",
  "invoice_id": null,
  "confidential": false,
  "site": { "type": "onsite", "address": "24500 Dana Point Harbor Dr, Dana Point, CA",
            "travel_zone": "zone_1", "access_notes": "Slip B; forklift unavailable" },
  "scope": {
    "objects": [{ "name": "hull section, port quarter", "size_mm": [2400, 900, 700],
                  "material": "gelcoat, glossy white", "features": ["through-hull", "chine" ] }],
    "deliverables": ["mesh_stl", "step_solid", "pdf_dimensional_report"],
    "tolerance_mm": 0.5,
    "purpose": "reverse engineering a replacement fairing",
    "units_out": "mm",
    "coordinate_origin": "keel centerline at station 4"
  },
  "schedule": { "scan_date": "2026-09-12", "due_date": "2026-09-26", "rush": false },
  "money": { "quoted": 3450.00, "deposit": 1725.00, "deposit_paid": true, "invoiced": null, "paid": null },
  "assets_root": "$SCAN_ROOT/SC-2026-001",
  "history": [{ "ts": "2026-09-08T15:12:00Z", "by": "billing-clerk", "from": "accepted", "to": "scheduled" }]
}
```

## Key field notes

- `scope.tolerance_mm` is the **contracted** tolerance. `cad-qa` compares measured
  deviation against it and fails the job if exceeded. Never set it tighter than the
  equipment envelope in `equipment.json`.
- `scope.units_out` and `scope.coordinate_origin` are the two things clients complain
  about most. They are required fields; intake must capture them or ask.
- `site.travel_zone` keys into `service-area.json` and drives the travel line item.
- `confidential: true` permanently blocks the job from portfolio/marketing use.
- `assets.json` entries carry `sha256`, `bytes`, and `tier` (`working` | `archive`) so a
  missing file is detectable without opening the NAS.
