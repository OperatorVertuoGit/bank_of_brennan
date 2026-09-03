# Henderson Tilt-Up Survey Database

Airtable schema and pipeline for a queryable geospatial database of survey points and
lines from a tilt-up construction project in Henderson, NV, published to a Mapbox webapp
with per-layer vector tiling.

## What's here

| Path | What it is |
|---|---|
| `docs/airtable-schema.md` | The schema. 13 tables, every field, formulas, views, limits. Start here. |
| `docs/mapbox-pipeline.md` | Airtable → GeoJSON → tiles → webapp, and what Airtable can't query. |
| `schema/airtable_schema.json` | Machine-readable schema. Single source of truth for the scripts. |
| `schema/seed_data.json` | Starting rows for the Layers registry (25) and Feature Codes (27). |
| `scripts/create_airtable_base.py` | Builds the base from the schema via the Metadata API. |
| `scripts/seed_reference_data.py` | Loads the layer registry and feature code dictionary. |
| `scripts/import_survey_csv.py` | PNEZD / linework CSV → Airtable, grid → WGS84. |
| `scripts/airtable_to_geojson.py` | Airtable → per-layer GeoJSON + `layers.json` + tippecanoe command. |
| `examples/` | Sample PNEZD and linework CSVs on real Henderson coordinates. |

## The shape of it

- **Airtable holds attributes and canonical coordinates. Mapbox holds rendered geometry.**
  A status change recolors the map without a re-tile, via `promoteId` + `setFeatureState`.
- **Points and lines are separate tables** — their attributes genuinely differ, and a merged
  table leaves half its fields null on every row.
- **Coordinates are stored twice on purpose**: the surveyor's Northing/Easting/Elevation
  (never derived) and WGS84 lon/lat (derived once at import, the only thing Mapbox reads).
- **A `Layers` table drives the map.** Adding a layer is an Airtable row, not a deploy.
- **Tilt-up specifics are first class**: panel register with casting and erection sequence,
  lift inserts, brace anchors, embeds, plumb and joint-width QA, and design-vs-as-built
  Δ N/E/Z against per-feature-code tolerances.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # fill in AIRTABLE_PAT and AIRTABLE_WORKSPACE_ID
set -a; source .env; set +a

python scripts/create_airtable_base.py --name "Henderson Tilt-Up Survey"
# note the base id it prints, add it to .env as AIRTABLE_BASE_ID, then:
python scripts/seed_reference_data.py
```

`create_airtable_base.py` prints a checklist of the ~23 formula, rollup, lookup, and count
fields the Metadata API cannot create, each with the exact expression to paste.

## Before importing anything

Confirm the coordinate system with the surveyor of record, then prove the transform on one
known point:

```bash
python scripts/import_survey_csv.py --check <NORTHING> <EASTING> --epsg 3421
```

Clark County is the Nevada East zone. `EPSG:3421` (NAD83) and `EPSG:6428` (NAD83(2011)) are
the usual candidates, both in US survey feet. Two things routinely break Henderson jobs: US
survey foot vs. international foot, and a scaled **ground** system that looks like state
plane but carries a combined factor and a false origin — no EPSG code describes that one, and
you need the surveyor's calibration parameters instead.

## Import and publish

```bash
python scripts/import_survey_csv.py points examples/sample_points_pnezd.csv \
    --epsg 3421 --area BLDG-A --session SS-2026-0142 --preview out/preview.geojson
# eyeball the preview, then
python scripts/import_survey_csv.py points examples/sample_points_pnezd.csv \
    --epsg 3421 --area BLDG-A --session SS-2026-0142 --commit

python scripts/airtable_to_geojson.py --out out/ --tileset you.henderson-survey
./out/tippecanoe.sh
```

Imports are idempotent — Feature IDs are derived from the surveyor's own point and line
numbers, so re-running updates in place rather than duplicating.

## Caveats

- Tolerances in `schema/seed_data.json` are typical tilt-up values, not your contract.
  Replace them with your project spec before anyone relies on the QC formulas.
- Airtable is not a spatial database: no spatial index, no proximity search. See
  `docs/mapbox-pipeline.md` §7 for what to do instead. At this data volume, turf.js in the
  browser covers it.
- Never ship an Airtable PAT to the browser. Proxy through a serverless function —
  `docs/mapbox-pipeline.md` §6.
