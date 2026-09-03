# Airtable Schema — Henderson, NV Tilt-Up Survey Database

Source of truth for survey attributes; geometry is exported to GeoJSON and tiled for Mapbox.
Sized for ~2–10k point/line features on one site.

---

## 0. Design decisions (read first)

**Airtable holds attributes + canonical coordinates. Mapbox holds rendered geometry.**
You do not re-tile every time a status changes. Tiles carry a stable `feature_id`; the
webapp joins live Airtable attributes onto tiles with `promoteId` + `setFeatureState`.
Re-tile only when geometry is added, moved, or voided.

**Two geometry tables, not one.** Points and lines have genuinely different attributes
(a line has bearing/grade/length/invert; a point has Δ N/E/Z tolerance checks). Airtable
has no geometry type, so a single "Features" table forces half its fields to be null on
every row and makes the layer registry ambiguous. Split them.

**Coordinates are stored twice, on purpose.**
- `Northing` / `Easting` / `Elevation` — the surveyor's grid coordinates. This is what the
  field crew, the GC, and the shop drawings speak. Never derived, never rounded.
- `Longitude` / `Latitude` — WGS84 decimal degrees, derived by the import script. This is
  the only thing Mapbox can consume.
Store both; transform once at ingest, not at render time.

**A Layers table drives the map, not hardcoded JS.** Adding a layer to the webapp should
be an Airtable row, not a deploy.

**Record IDs.** Every geometry row gets a human-readable `Feature ID` (`PT-A-00412`) used
as the tile `promoteId`. Airtable's `rec…` ID also travels in the GeoJSON as `airtable_id`
so a map click can deep-link back to the record.

---

## 1. Table inventory

| # | Table | Purpose | Est. rows |
|---|-------|---------|-----------|
| 1 | Projects | Top-level container, CRS, map extent | 1–5 |
| 2 | Areas | Buildings / phases / yards; carries the building grid | 5–30 |
| 3 | Coordinate Systems | CRS reference + site calibration | 2–5 |
| 4 | Survey Sessions | Field visit provenance and QC | 50–500 |
| 5 | Control Points | Control & benchmarks (kept apart from features) | 10–100 |
| 6 | Layers | Map layer registry — drives Mapbox styling | 15–40 |
| 7 | Feature Codes | Field code dictionary + tolerances | 30–80 |
| 8 | Point Features | Main point table | 1k–10k |
| 9 | Line Features | Main line table | 100–2k |
| 10 | Panels | Tilt-up panel register | 50–400 |
| 11 | Embeds | Embed/insert fabrication + QA detail | 200–3k |
| 12 | Export Batches | Tileset build log | 20–200 |
| 13 | Issues | Out-of-tolerance, conflicts, rework | 10–500 |

Tables 11 and 13 are optional at launch. 1–10 and 12 are the working core.

---

## 2. Projects

Primary field: **Project Name** (single line text)

| Field | Type | Notes |
|---|---|---|
| Project Name | Single line text | Primary |
| Project Number | Single line text | Your job number |
| Client / Owner | Single line text | |
| General Contractor | Single line text | |
| Address | Single line text | |
| City | Single line text | Henderson |
| County | Single line text | Clark |
| State | Single line text | NV |
| APN | Single line text | Assessor parcel number |
| Status | Single select | Preconstruction, Active, Punch, Closeout, Archived |
| Horizontal CRS | Link → Coordinate Systems | |
| Vertical Datum | Single line text | e.g. NAVD88 (Geoid18) |
| Basis of Bearing | Long text | Verbatim from the record of survey |
| Site Benchmark | Link → Control Points | |
| Site Calibration File | Attachment | `.dc` / `.cal` / localization |
| Combined Scale Factor | Number (precision 8) | Ground-to-grid; Vegas valley sites often run a ground system |
| Start Date | Date | |
| Target Completion | Date | |
| Map Center Lon | Number (precision 8) | Webapp initial view |
| Map Center Lat | Number (precision 8) | |
| Map Default Zoom | Number (precision 1) | |
| BBox W / S / E / N | Number (precision 8) ×4 | `fitBounds` on load |
| Mapbox Tileset ID | Single line text | `mapbox://you.henderson-survey` |
| Areas | Link → Areas | |
| Survey Sessions | Link → Survey Sessions | |
| Point Features | Link → Point Features | |
| Line Features | Link → Line Features | |
| Notes | Long text | |

---

## 3. Areas

Primary field: **Area Code** (e.g. `BLDG-A`, `PH2-YARD`)

| Field | Type | Notes |
|---|---|---|
| Area Code | Single line text | Primary |
| Area Name | Single line text | |
| Project | Link → Projects | |
| Type | Single select | Building, Parking, Yard, Offsite, Utility Corridor, Phase, Detention |
| Building Footprint SF | Number (precision 0) | |
| Finish Floor Elevation | Number (precision 3) | NAVD88 ft |
| Grid Origin Northing | Number (precision 3) | Intersection of grid A/1 |
| Grid Origin Easting | Number (precision 3) | |
| Grid Rotation (deg) | Number (precision 6) | Building grid azimuth vs. state plane north — **required**, tilt-up sites are almost never grid-north |
| Panel Count | Rollup (count of Panels) | |
| Panels Erected | Rollup (count where Set Status is Erected+) | |
| Erection % | Formula | `IF({Panel Count}=0, 0, {Panels Erected}/{Panel Count})` — format as percent |
| Status | Single select | Not Started, Sitework, Foundations, Slab, Casting, Erecting, Complete |
| Panels | Link → Panels | |
| Point Features | Link → Point Features | |
| Line Features | Link → Line Features | |

Grid rotation is what lets the webapp draw a building-grid overlay and lets the import
script convert grid-relative callouts ("3 ft east of line B") into coordinates.

---

## 4. Coordinate Systems

Primary field: **CRS Name**

| Field | Type | Notes |
|---|---|---|
| CRS Name | Single line text | `NAD83(2011) / Nevada East (ftUS)` |
| EPSG Code | Number (precision 0) | See caution below |
| Type | Single select | Projected, Geographic, Local/Ground |
| Linear Unit | Single select | US survey foot, International foot, Meter |
| Vertical Datum | Single line text | NAVD88 |
| Geoid Model | Single line text | Geoid18 |
| PROJ String | Long text | Pasted from the surveyor or epsg.io |
| WKT | Long text | |
| Is Ground System | Checkbox | True if scaled/translated from grid |
| Combined Factor | Number (precision 9) | |
| Origin Shift N / E | Number (precision 3) ×2 | For ground systems with a false origin |
| Verified By | Single line text | Surveyor of record |
| Verified Date | Date | |

> **Caution — confirm the EPSG code with your surveyor before you transform anything.**
> Clark County falls in the **Nevada East** zone. Common candidates are
> `EPSG:3421` (NAD83 / Nevada East, ftUS) and `EPSG:6428` (NAD83(2011) / Nevada East, ftUS).
> Two things routinely break Henderson jobs: (a) US survey foot vs. international foot,
> which drifts ~0.01 ft per 5,000 ft of easting, and (b) a **ground** coordinate system
> that looks like state plane but carries a combined factor and a false origin. If your
> points land in the Pacific Ocean or 40 ft off, it is one of these two. Transform one
> known control point first and check it against a known lat/lon before you import 4,000
> rows.

---

## 5. Survey Sessions

Primary field: **Session ID** (`SS-2026-0142`)

| Field | Type | Notes |
|---|---|---|
| Session ID | Single line text | Primary |
| Date | Date | |
| Project | Link → Projects | |
| Areas | Link → Areas | |
| Crew Chief | Single line text or Collaborator | |
| Crew | Single line text | |
| Instrument | Single select | Trimble R12i, Trimble SX12, Leica TS16, Total Station (other), GNSS Rover, UAV Photogrammetry, Terrestrial Scan |
| Method | Single select | Network RTK/VRS, Base+Rover RTK, Static, TS Traverse, TS Radial, Level Loop, Scan, Photogrammetry |
| Base / Control Used | Link → Control Points | |
| Localization Applied | Checkbox | |
| Check Shot Point | Link → Control Points | |
| Check Δ Horizontal (ft) | Number (precision 3) | |
| Check Δ Vertical (ft) | Number (precision 3) | |
| Session QC | Formula | Pass/Fail on check deltas — see §14 |
| Closure Error | Number (precision 4) | Traverse/level loop |
| Raw Data File | Attachment | `.job`, `.dc`, `.rw5`, `.csv` |
| Weather / PDOP Notes | Long text | |
| Approved By | Single line text | |
| Approved Date | Date | |
| Point Count | Count (Point Features) | |
| Line Count | Count (Line Features) | |
| Notes | Long text | |

Every geometry row links to exactly one session. When a shot is later found to be bad,
you can void a whole session's worth of points in one filter instead of hunting rows.

---

## 6. Control Points

Kept separate from Point Features because control has different QA weight, different
lifecycle, and should never be filtered away by accident.

Primary field: **Point ID** (`CP-101`, `BM-1`)

| Field | Type | Notes |
|---|---|---|
| Point ID | Single line text | Primary |
| Type | Single select | Primary Control, Secondary Control, Benchmark, Site Monument, Property Corner, Reference Point, Temporary |
| Project | Link → Projects | |
| Northing | Number (precision 3) | |
| Easting | Number (precision 3) | |
| Elevation | Number (precision 3) | NAVD88 ft |
| Longitude | Number (precision 8) | WGS84, derived |
| Latitude | Number (precision 8) | WGS84, derived |
| Order / Class | Single select | 1st, 2nd, 3rd, Local |
| Monument Type | Single select | Rebar w/ Cap, Mag Nail, Hub & Tack, Brass Disc, Control Point (X), PK Nail, Iron Pipe |
| Established By | Single line text | |
| Established Date | Date | |
| Status | Single select | Active, Recovered, Disturbed, Destroyed, Superseded |
| Last Verified | Date | |
| Verify Δ H / Δ V (ft) | Number (precision 3) ×2 | |
| Description | Long text | To-reach description |
| Photo | Attachment | |
| Sessions | Link → Survey Sessions | Sessions that occupied or checked this point |
| Layer | Link → Layers | Usually `control` |

---

## 7. Layers  ← the table that drives the map

One row per Mapbox source-layer. The webapp reads this table at load and builds its layer
list, legend, and paint properties from it. Adding a layer is a row, not a deploy.

Primary field: **Layer ID** — lowercase slug, must match the tippecanoe `-l` name exactly.

| Field | Type | Notes |
|---|---|---|
| Layer ID | Single line text | Primary. `as-built-embeds`, `gridlines`, `utilities-storm` |
| Display Name | Single line text | Shown in the layer switcher |
| Geometry Type | Single select | Point, LineString, Polygon |
| Category | Single select | Control, Layout, As-Built, Design, Structural, Utilities, Sitework, Topo, Reference |
| Discipline | Single select | Survey, Concrete, Structural, Civil, MEP, Architectural |
| Tileset ID | Single line text | `mapbox://you.henderson-survey` |
| Source Layer | Single line text | The name inside the tileset |
| Min Zoom | Number (precision 0) | Layer `minzoom` |
| Max Zoom | Number (precision 0) | |
| Draw Order | Number (precision 0) | Ascending = bottom to top |
| Color | Single line text | Hex `#E4572E` |
| Color By Status | Checkbox | If true, app uses the status ramp instead of Color |
| Line Width | Number (precision 1) | px at z16 |
| Line Dash | Single line text | `2,2` or blank for solid |
| Circle Radius | Number (precision 1) | Points |
| Icon Name | Single line text | Sprite name, blank = circle |
| Opacity | Number (precision 2) | 0–1 |
| Visible By Default | Checkbox | |
| In Layer Switcher | Checkbox | |
| Clusterable | Checkbox | For dense as-built/topo point layers |
| Label Field | Single line text | Field to render as a symbol label |
| Popup Fields | Long text | JSON array: `["Feature ID","Feature Code","Elevation","QC Result"]` |
| Filter Expression | Long text | Optional raw Mapbox filter JSON |
| Legend Group | Single line text | Groups rows in the legend |
| Feature Count | Rollup | From Point/Line Features |
| Point Features | Link → Point Features | |
| Line Features | Link → Line Features | |
| Notes | Long text | |

### Suggested starting layer set

| Layer ID | Geom | Category | Notes |
|---|---|---|---|
| `control` | Point | Control | Always on, always on top |
| `benchmarks` | Point | Control | |
| `gridlines` | LineString | Layout | Building grid, labeled |
| `panel-footprints` | LineString | Structural | Colored by Set Status |
| `panel-layout-points` | Point | Layout | Panel base corners |
| `brace-anchors` | Point | Structural | Brace floor inserts |
| `lift-inserts` | Point | Structural | |
| `embeds-design` | Point | Design | |
| `embeds-asbuilt` | Point | As-Built | Colored by QC Result |
| `anchor-bolts` | Point | As-Built | |
| `footing-lines` | LineString | Structural | |
| `pier-centers` | Point | Structural | |
| `slab-edge` | LineString | Structural | |
| `slab-elevations` | Point | As-Built | FF/FL shots, clusterable |
| `saw-cuts` | LineString | Structural | |
| `utilities-storm` | LineString | Utilities | |
| `utilities-sanitary` | LineString | Utilities | |
| `utilities-water` | LineString | Utilities | |
| `utilities-dry` | LineString | Utilities | Electrical / comm / gas |
| `utility-structures` | Point | Utilities | MHs, CBs, valves — inverts |
| `curb-flowline` | LineString | Sitework | |
| `topo` | Point | Topo | Clusterable, high minzoom |
| `property-boundary` | LineString | Reference | |
| `easements` | LineString | Reference | |
| `crane-paths` | LineString | Layout | Pick and travel routes |

---

## 8. Feature Codes

Your field code dictionary. Crews already shoot codes; this makes the code the join key
between the data collector and the map, and it is where tolerances live.

Primary field: **Code** (`EMB`, `AB`, `GRD`, `FTG`, `INV`, `TOPO`)

| Field | Type | Notes |
|---|---|---|
| Code | Single line text | Primary. Must match the data collector's code exactly |
| Description | Single line text | |
| Geometry Type | Single select | Point, LineString |
| Layer | Link → Layers | Determines which tile layer the feature lands in |
| Discipline | Single select | |
| Tolerance H (ft) | Number (precision 4) | Drives the QC formula |
| Tolerance V (ft) | Number (precision 4) | |
| Tolerance Source | Single line text | e.g. `ACI 117 §2.3`, `PCI MNL-135`, `spec 03 45 00` |
| Required Attributes | Long text | Comma list the import script validates |
| Requires Panel Link | Checkbox | Forces embeds/inserts to name a panel |
| Active | Checkbox | |
| Point Features | Link → Point Features | |
| Line Features | Link → Line Features | |

Representative tilt-up tolerances to seed with — **confirm against your project spec, these
are typical values, not your contract**:

| Code | Description | Tol H | Tol V |
|---|---|---|---|
| `AB` | Anchor bolt | 0.021 (¼") | 0.042 (½") |
| `EMB` | Embed plate | 0.083 (1") | 0.083 (1") |
| `LIFT` | Lift insert | 0.021 (¼") | 0.021 (¼") |
| `BRC` | Brace floor anchor | 0.167 (2") | 0.083 (1") |
| `PNLC` | Panel base corner | 0.021 (¼") | 0.021 (¼") |
| `FTG` | Footing line | 0.083 (1") | 0.083 (1") |
| `PIER` | Pier center | 0.042 (½") | 0.042 (½") |
| `FF` | Finish floor shot | — | 0.021 (¼") |
| `INV` | Utility invert | 0.083 (1") | 0.021 (¼") |
| `GRD` | Gridline | 0.010 | — |
| `TOPO` | Topo shot | 0.10 | 0.10 |

---

## 9. Point Features

The main table. Primary field: **Feature ID** — `PT-{AreaCode}-{5-digit}`, assigned by the
import script so it is stable across re-imports. This is the Mapbox `promoteId`.

### Identity
| Field | Type | Notes |
|---|---|---|
| Feature ID | Single line text | Primary, unique, stable |
| Point Number | Number (precision 0) | The crew's raw point number |
| Feature Code | Link → Feature Codes | |
| Layer | Link → Layers | Set by the import script from Feature Code |
| Project / Area / Panel | Link ×3 | Panel blank for non-panel work |
| Survey Session | Link → Survey Sessions | |

### Geometry
| Field | Type | Notes |
|---|---|---|
| Northing | Number (precision 3) | Grid, ft |
| Easting | Number (precision 3) | Grid, ft |
| Elevation | Number (precision 3) | NAVD88 ft |
| Longitude | Number (precision 8) | WGS84, derived at import |
| Latitude | Number (precision 8) | WGS84, derived at import |
| Geometry Source | Single select | Field Shot, Design/Model, Calculated, Digitized |

Do **not** build the GeoJSON string in an Airtable formula. Airtable formula
number-to-string conversion follows the field's display precision, which silently truncates
longitude to a few decimals — that is a 30-ft error on the ground. The export script builds
the geometry from the raw numeric values.

### Design vs. as-built (the tilt-up QA core)
| Field | Type | Notes |
|---|---|---|
| Design Northing / Easting / Elevation | Number (precision 3) ×3 | From the model |
| Δ N | Formula | `IF(AND({Design Northing}, {Northing}), {Northing}-{Design Northing}, BLANK())` |
| Δ E | Formula | same pattern |
| Δ Z | Formula | same pattern |
| Δ H | Formula | `IF(AND({Δ N},{Δ E}), SQRT({Δ N}^2+{Δ E}^2), BLANK())` |
| Tolerance H / V | Lookup ← Feature Code | |
| QC Result | Formula | Pass / Fail / Not Checked — see §14 |
| QC Checked By | Single line text | |
| QC Checked Date | Date | |

### Status & accuracy
| Field | Type | Notes |
|---|---|---|
| Status | Single select | Design, Staked, As-Built, Verified, Out of Tolerance, Superseded, Void |
| Solution Type | Single select | RTK Fixed, RTK Float, Autonomous, Static, Total Station, Scan, Derived |
| Accuracy H (ft) | Number (precision 3) | From the data collector |
| Accuracy V (ft) | Number (precision 3) | |
| Superseded By | Link → Point Features (self) | |
| Revision | Number (precision 0) | |

### Content
| Field | Type | Notes |
|---|---|---|
| Description | Long text | Field note |
| Photos | Attachment | |
| Issues | Link → Issues | |
| Embed | Link → Embeds | 1:1 when the point is an embed |

### Publishing
| Field | Type | Notes |
|---|---|---|
| Include in Tileset | Checkbox | Default checked; uncheck to hide without deleting |
| Last Exported | Date | Stamped by the export script |
| Export Batch | Link → Export Batches | |
| Airtable Record ID | Formula | `RECORD_ID()` — travels into the GeoJSON for deep links |

### Views to create
- `Map Export` — filter `Include in Tileset` is checked AND `Status` is not Void/Superseded
- `Out of Tolerance` — `QC Result` = Fail, grouped by Panel
- `Unverified As-Builts` — `Status` = As-Built AND `QC Checked Date` is empty
- `Today's Shots` — grouped by Survey Session, sorted desc
- `Missing Coordinates` — `Longitude` is empty (import failures)

---

## 10. Line Features

Primary field: **Feature ID** — `LN-{AreaCode}-{5-digit}`

| Field | Type | Notes |
|---|---|---|
| Feature ID | Single line text | Primary |
| Feature Code | Link → Feature Codes | |
| Layer | Link → Layers | |
| Project / Area / Panel | Link ×3 | |
| Survey Session | Link → Survey Sessions | |
| Line Type | Single select | Gridline, Panel Footprint, Panel Joint, Footing, Slab Edge, Saw Cut, Curb/Flowline, Utility Run, Property Line, Easement, Setback, Fence, Crane Path, Fire Lane, Offset Line, Breakline |
| Geometry GeoJSON | Long text | `[[lon,lat],[lon,lat],…]` WGS84, written by the import script |
| Vertex Coordinates (Grid) | Long text | `[[N,E,Z],…]` — the surveyor-facing copy |
| Vertex Count | Number (precision 0) | |
| Length (ft) | Number (precision 3) | 2D ground length |
| Start N / E / Z | Number (precision 3) ×3 | |
| End N / E / Z | Number (precision 3) ×3 | |
| Bearing | Single line text | `N 43°17'22" E` |
| Grade % | Number (precision 3) | |
| Grid Label | Single line text | `A`, `B`, `1`, `12.5` — for gridlines |
| Start Point / End Point | Link → Point Features ×2 | Optional |

### Utility subset (null for non-utility lines)
| Field | Type | Notes |
|---|---|---|
| Utility Type | Single select | Storm, Sanitary, Water, Fire, Gas, Electrical, Comm, Irrigation, Unknown |
| Pipe Size (in) | Number (precision 2) | |
| Pipe Material | Single select | RCP, PVC, HDPE, DIP, CMP, Copper, Conduit |
| Invert Start / End | Number (precision 3) ×2 | |
| Cover at Start / End (ft) | Number (precision 2) ×2 | |
| Utility Status | Single select | Existing, New, Abandoned, Potholed, Located (paint/SUE), Unknown |
| SUE Quality Level | Single select | A, B, C, D |

### Status / publishing (same pattern as points)
`Status`, `Design Line` (link → self), `Description`, `Photos`, `Issues`,
`Include in Tileset`, `Last Exported`, `Export Batch`, `Airtable Record ID`.

**Long-text limit:** an Airtable long text field caps at 100,000 characters. A WGS84
vertex pair is ~26 chars, so a line safely holds ~3,500 vertices. Site lines and gridlines
are nowhere near that. Dense scan breaklines can exceed it — for those, keep the geometry
in the GeoJSON/tile pipeline and store only attributes plus an endpoint pair in Airtable.
The export script warns at 90k characters.

---

## 11. Panels (tilt-up)

Primary field: **Panel Mark** (`A-14`)

### Identity & geometry
| Field | Type | Notes |
|---|---|---|
| Panel Mark | Single line text | Primary |
| Project / Area | Link ×2 | |
| Panel Type | Single select | Solid, Window, Door, Dock, Corner, Return, Parapet, Reveal, Spandrel |
| Width (ft) | Number (precision 3) | |
| Height (ft) | Number (precision 3) | |
| Thickness (in) | Number (precision 2) | |
| Area (SF) | Formula | `{Width}*{Height}` |
| Weight (lbs) | Formula | `{Width}*{Height}*({Thickness}/12)*150` — 150 pcf; subtract openings manually or add an `Opening SF` field |
| Opening SF | Number (precision 1) | |
| Net Weight (lbs) | Formula | `({Area}-{Opening SF})*({Thickness}/12)*150` |

### Casting & erection
| Field | Type | Notes |
|---|---|---|
| Casting Bed | Single line text | Slab area or stack ID |
| Stack Position | Number (precision 0) | Position in the stack, bottom = 1 |
| Cast Sequence | Number (precision 0) | |
| Cast Date | Date | |
| Strip Date | Date | |
| Erection Sequence | Number (precision 0) | |
| Crane Pick # | Number (precision 0) | |
| Erection Date | Date | |
| Set Status | Single select | Not Cast, Cast, Cured, Stripped, Staged, Erected, Braced, Welded, Grouted, Braces Removed, Patched, Accepted |
| Rigging Type | Single select | 2-point, 4-point, 6-point, 8-point, Strongback, Spreader Bar |
| Lift Insert Count | Number (precision 0) | |
| Lift Inserts | Link → Point Features | |
| Brace Count | Number (precision 0) | |
| Brace Anchors | Link → Point Features | Floor-anchor locations |
| Base Layout Points | Link → Point Features | |
| Panel Footprint | Link → Line Features | |
| Embeds | Link → Embeds | |

### As-built QA
| Field | Type | Notes |
|---|---|---|
| As-Built Base Elev L / R | Number (precision 3) ×2 | |
| Plumb Deviation (in) | Number (precision 3) | Top vs. base, out-of-plumb |
| Joint Width Left / Right (in) | Number (precision 3) ×2 | |
| Panel Top Elevation | Number (precision 3) | |
| Alignment Δ (in) | Number (precision 3) | Face offset from the layout line |
| Plumb Tolerance (in) | Number (precision 3) | Default 0.25 per 10 ft, confirm against spec |
| Panel QC | Formula | Pass / Fail / Not Checked |
| Shop Drawing | Attachment | |
| Photos | Attachment | |
| Issues | Link → Issues | |
| Notes | Long text | |

### Views
- `Erection Sequence` — sorted by Erection Sequence, grouped by Area
- `Casting Board` — Kanban by Set Status
- `Not Yet Braced` — Set Status is Erected, grouped by crane pick
- `Panel QA Fails` — Panel QC = Fail

---

## 12. Embeds (optional but recommended)

Splits *where it is* (a Point Feature) from *what it is and did it pass* (an Embed record).
Keeps Point Features from carrying a dozen fields that are null on 90% of rows.

| Field | Type | Notes |
|---|---|---|
| Embed Mark | Single line text | Primary. `E-14-03` |
| Panel | Link → Panels | |
| Point Feature | Link → Point Features | The geospatial location |
| Embed Type | Single select | Plate, Angle, Weld Plate, Lift Insert, Brace Insert, Rebar Dowel, Sleeve, Blockout, Coil Insert, Ferrule |
| Size / Detail | Single line text | `PL 8×8×½ w/ (4) ½"×4" HAS` |
| Elevation Above Panel Base (ft) | Number (precision 3) | |
| Offset From Panel Left Edge (ft) | Number (precision 3) | Panel-relative coords — how the shop drawing reads |
| Face | Single select | Interior, Exterior, Edge, Top, Bottom |
| Required Weld | Single line text | |
| Installed | Checkbox | |
| Installed Date | Date | |
| Welded | Checkbox | |
| Weld Inspected | Checkbox | |
| Inspector | Single line text | |
| As-Built Δ (in) | Number (precision 3) | Rollup or manual from the linked point |
| Embed QC | Single select | Pass, Fail, Rework, Not Checked |
| Photos | Attachment | |
| Notes | Long text | |

---

## 13. Export Batches

The tileset build log. Without it you cannot answer "which tiles is the map serving right now".

| Field | Type | Notes |
|---|---|---|
| Batch ID | Single line text | Primary. `EXP-2026-0903-01` |
| Created | Created time | |
| Triggered By | Single line text | |
| Project | Link → Projects | |
| Layers Included | Link → Layers | |
| Point Count / Line Count | Number (precision 0) ×2 | |
| GeoJSON Bundle | Attachment | The exact input, archived |
| Tileset ID | Single line text | |
| Tileset Version | Single line text | |
| Recipe / Command | Long text | The literal tippecanoe or MTS recipe used |
| Status | Single select | Queued, Processing, Published, Failed |
| Published At | Date | |
| Log | Long text | |
| Point Features / Line Features | Link ×2 | What went into this batch |

---

## 14. Formulas

Airtable formula syntax, paste as-is.

**Point QC Result**
```
IF(
  OR({Design Northing} = BLANK(), {Northing} = BLANK()),
  "Not Checked",
  IF(
    AND(
      OR({Tolerance H} = BLANK(), {Δ H} <= {Tolerance H}),
      OR({Tolerance V} = BLANK(), ABS({Δ Z}) <= {Tolerance V})
    ),
    "Pass",
    "Fail"
  )
)
```

**Δ N** (Δ E and Δ Z follow the same shape)
```
IF(AND({Design Northing} != BLANK(), {Northing} != BLANK()), {Northing} - {Design Northing}, BLANK())
```

**Δ H**
```
IF(AND({Δ N} != BLANK(), {Δ E} != BLANK()), SQRT(POWER({Δ N}, 2) + POWER({Δ E}, 2)), BLANK())
```

**Δ H in inches** (what the field actually asks for)
```
IF({Δ H} != BLANK(), ROUND({Δ H} * 12, 3), BLANK())
```

**Session QC**
```
IF(
  OR({Check Δ Horizontal (ft)} = BLANK(), {Check Δ Vertical (ft)} = BLANK()),
  "No Check Shot",
  IF(AND(ABS({Check Δ Horizontal (ft)}) <= 0.08, ABS({Check Δ Vertical (ft)}) <= 0.10), "Pass", "Fail")
)
```
0.08 ft / 0.10 ft are typical RTK check-shot limits; set them to your own QC standard.

**Panel QC**
```
IF(
  {Plumb Deviation (in)} = BLANK(),
  "Not Checked",
  IF(ABS({Plumb Deviation (in)}) <= {Plumb Tolerance (in)}, "Pass", "Fail")
)
```

**Airtable Record ID** (on Point Features, Line Features, Panels)
```
RECORD_ID()
```

---

## 15. Status color ramp

Used by the webapp when a layer has `Color By Status` checked. Keep it in one place so the
map, the legend, and the Airtable field colors agree.

| Status | Hex | Meaning |
|---|---|---|
| Design | `#94A3B8` | Slate — model only, nothing built |
| Staked | `#3B82F6` | Blue — laid out in the field |
| As-Built | `#8B5CF6` | Violet — shot, not yet checked |
| Verified | `#10B981` | Green — checked, in tolerance |
| Out of Tolerance | `#EF4444` | Red |
| Superseded | `#D1D5DB` | Light grey |
| Void | `#F3F4F6` | Near-white, normally filtered out |

Panel Set Status uses a build-progress ramp instead: Not Cast `#E5E7EB` → Cast `#FCD34D` →
Stripped `#FBBF24` → Erected `#60A5FA` → Braced `#3B82F6` → Welded `#8B5CF6` →
Grouted `#34D399` → Accepted `#10B981`.

---

## 16. Relationship map

```
Projects ──┬── Areas ──┬── Panels ──┬── Embeds ── Point Features
           │           │            └── Point Features (inserts, anchors, base pts)
           │           │            └── Line Features (footprint, joints)
           │           ├── Point Features
           │           └── Line Features
           ├── Coordinate Systems
           ├── Control Points ──── Survey Sessions
           ├── Survey Sessions ──┬── Point Features
           │                     └── Line Features
           └── Export Batches ───┬── Point Features
                                 └── Line Features

Layers ──┬── Point Features        Feature Codes ──┬── Point Features
         ├── Line Features                         ├── Line Features
         └── Control Points                        └── Layers

Issues ──┬── Point Features / Line Features / Panels / Areas
```

---

## 17. Airtable operating limits worth knowing at this scale

- **Records per base:** 1,250 (Free) / 50,000 (Team) / 125,000 (Business) / 500,000 (Enterprise).
  A few thousand features plus panels and sessions fits Team comfortably. Topo point clouds
  do not — leave dense topo out of Airtable and in the tile pipeline.
- **API:** 5 requests/second per base; writes batch 10 records per request. A 4,000-point
  import is ~400 requests ≈ 80 seconds. The import script rate-limits itself.
- **Long text:** 100,000 characters — see the vertex note in §10.
- **Attachments:** don't put the full raw survey file set in Airtable; link to cloud storage
  and attach only the record-of-work file per session.
- **Linked records:** a single link cell holds many records fine, but a Panel linking 4,000
  points is slow to render. The links above are deliberately narrow.
- Airtable is not a spatial database. There is no spatial index, no `ST_Intersects`, no
  proximity search. If you eventually need "every embed within 5 ft of gridline B", that
  query belongs in PostGIS with Airtable as the attribute front end. At a few thousand
  features, you don't need it yet.
