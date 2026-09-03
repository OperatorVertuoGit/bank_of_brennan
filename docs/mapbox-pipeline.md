# Airtable → Mapbox pipeline

How the schema in `docs/airtable-schema.md` becomes a queryable map.

---

## 1. Data flow

```
 data collector CSV ──┐
 (PNEZD / linework)   │
                      ├─→ import_survey_csv.py ──→ Airtable  (attributes + coords)
 design model export ─┘        (grid → WGS84)         │
                                                      │  airtable_to_geojson.py
                                                      ▼
                                        out/geojson/<layer>.geojson
                                        out/layers.json
                                        out/tippecanoe.sh
                                                      │
                                            tippecanoe / MTS
                                                      ▼
                                        Mapbox tileset (one per project,
                                         one source-layer per Layers row)
                                                      │
                                                      ▼
  webapp:  style built from layers.json  +  live attributes via setFeatureState
                                                      ▲
                                                      └── /api/features (serverless
                                                          proxy → Airtable, cached)
```

Geometry goes through the tile pipeline. Attributes come live from Airtable. That split is
the whole design: a status change should recolor the map in seconds without a re-tile.

---

## 2. Do you even need vector tiles?

At a few thousand features, honestly: not yet.

| Features | Approach | Why |
|---|---|---|
| < ~5k | GeoJSON source loaded straight into the map | One file per layer, no tiling step, sub-second load. Attributes are live because the GeoJSON *is* the query result. |
| 5k–50k | Vector tiles, attributes via feature-state | GeoJSON parsing starts costing frame time on tablets in the field |
| > 50k, or topo/scan | Vector tiles, non-negotiable | Browser cannot hold it |

Start on GeoJSON. `airtable_to_geojson.py` writes exactly what you need for both paths, so
switching later is a config change, not a rewrite. Build the tileset the first time a
field tablet stutters — not before.

The rest of this document assumes you eventually go to tiles, because the `promoteId`
pattern is worth setting up from day one either way.

---

## 3. Tiling

`airtable_to_geojson.py` writes `out/tippecanoe.sh` with the layer list already filled in:

```bash
tippecanoe -o tiles.mbtiles --force -Z10 -z22 \
  --no-feature-limit --no-tile-size-limit --generate-ids \
  -L control:geojson/control.geojson \
  -L gridlines:geojson/gridlines.geojson \
  -L panel-footprints:geojson/panel-footprints.geojson \
  ...
```

The flags matter:

- `-L <name>:<file>` — one **source-layer per Airtable Layers row**. This is what makes the
  layer switcher work. The name after `-L` must equal the `Layer ID` exactly.
- `-Z10 -z22` — construction data is useless zoomed out and needs to stay crisp at z22.
  Below z10 you don't need the site; above z22 Mapbox overzooms from z22 for free.
- `--no-feature-limit --no-tile-size-limit` — a dense embed layer inside one building is a
  single tile with a few thousand points. Without these, tippecanoe silently drops features
  to hit its size budget, and you will be looking at a map that is quietly missing embeds.
- **Never** `--drop-densest-as-needed` or `-r` on as-built data. Dropping points is fine for
  a heatmap and disqualifying for QA.

Upload with `mapbox upload <username>.<tileset> tiles.mbtiles`, or move to the Mapbox Tiling
Service with a recipe once the pipeline is on a schedule.

---

## 4. promoteId + feature-state — the part worth getting right

Tiles are immutable. Every re-tile is minutes of build plus a CDN cache cycle. You do not
want that in the loop when a foreman marks a panel braced.

Give each source a `promoteId` so `Feature ID` becomes the feature's addressable key:

```js
map.addSource('survey', {
  type: 'vector',
  url: 'mapbox://you.henderson-survey',
  promoteId: {
    'embeds-asbuilt': 'Feature ID',
    'panel-footprints': 'Feature ID',
    // one entry per source-layer
  },
});
```

Then paint from feature-state, falling back to the value baked into the tile:

```js
const STATUS_COLORS = {
  'Design':           '#94A3B8',
  'Staked':           '#3B82F6',
  'As-Built':         '#8B5CF6',
  'Verified':         '#10B981',
  'Out of Tolerance': '#EF4444',
  'Superseded':       '#D1D5DB',
};

map.addLayer({
  id: 'embeds-asbuilt',
  type: 'circle',
  source: 'survey',
  'source-layer': 'embeds-asbuilt',
  paint: {
    'circle-radius': 5,
    'circle-color': [
      'match',
      ['coalesce', ['feature-state', 'status'], ['get', 'Status'], 'Design'],
      ...Object.entries(STATUS_COLORS).flat(),
      '#94A3B8',
    ],
    'circle-stroke-width': ['case', ['boolean', ['feature-state', 'selected'], false], 2, 0],
    'circle-stroke-color': '#111827',
  },
});
```

Push live Airtable values in on load and on every poll:

```js
async function refreshState() {
  const rows = await fetch('/api/features?since=' + lastSync).then(r => r.json());
  for (const row of rows) {
    map.setFeatureState(
      { source: 'survey', sourceLayer: row.layer, id: row.featureId },
      { status: row.status, qc: row.qcResult, panelStatus: row.panelStatus },
    );
  }
  lastSync = new Date().toISOString();
}
```

Two constraints that bite people:

- `setFeatureState` only sticks for tiles that are currently loaded. Re-apply on
  `sourcedata` when new tiles arrive, or keep a state map and replay it.
- Feature-state cannot be used in a `filter`. Filters read tile properties only. If you need
  "show only failing embeds", either bake `QC Result` into the tile (it is in the default
  property list) or drive it with paint opacity instead of a filter.

---

## 5. Building the map from `layers.json`

`airtable_to_geojson.py` emits `out/layers.json` — the Layers table, resolved. The app loops
it instead of hardcoding layers:

```js
const layers = await fetch('/layers.json').then(r => r.json());

for (const L of layers.sort((a, b) => a.drawOrder - b.drawOrder)) {
  if (!L.hasData) continue;

  const base = {
    id: L.id,
    source: 'survey',
    'source-layer': L.sourceLayer,
    minzoom: L.minzoom,
    maxzoom: L.maxzoom,
    layout: { visibility: L.visible ? 'visible' : 'none' },
  };

  if (L.geometryType === 'Point') {
    map.addLayer({ ...base, type: 'circle', paint: {
      'circle-radius': L.circleRadius ?? 4,
      'circle-color': L.colorByStatus ? statusExpr() : L.color,
      'circle-opacity': L.opacity ?? 1,
    }});
  } else {
    map.addLayer({ ...base, type: 'line',
      layout: { ...base.layout, 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': L.colorByStatus ? statusExpr() : L.color,
        'line-width': L.lineWidth ?? 2,
        'line-opacity': L.opacity ?? 1,
        ...(L.lineDash ? { 'line-dasharray': L.lineDash } : {}),
      }});
  }

  if (L.labelField) {
    map.addLayer({ ...base, id: `${L.id}-label`, type: 'symbol',
      layout: { ...base.layout,
        'text-field': ['get', L.labelField],
        'text-size': 11, 'text-offset': [0, 1.1], 'text-allow-overlap': false },
      paint: { 'text-color': '#111827', 'text-halo-color': '#fff', 'text-halo-width': 1.2 }});
  }
}
```

The layer switcher, the legend, and the popup field list all come from the same array. Adding
`utilities-irrigation` to the map is a new Airtable row and a re-export — no deploy.

---

## 6. Reading Airtable from the browser

**Do not put the Airtable PAT in client-side code.** A PAT scoped to a base grants full read
and write to everything in it; anyone can pull it out of a JS bundle or a network tab.

Put a small serverless function between them (Vercel/Netlify/Cloudflare Worker):

```js
// /api/features  -- server side only
export default async function handler(req, res) {
  const since = req.query.since;
  const params = new URLSearchParams({ view: 'Map Export', pageSize: '100' });
  if (since) params.set('filterByFormula', `LAST_MODIFIED_TIME() > "${since}"`);

  const r = await fetch(
    `https://api.airtable.com/v0/${process.env.AIRTABLE_BASE_ID}/Point%20Features?${params}`,
    { headers: { Authorization: `Bearer ${process.env.AIRTABLE_PAT}` } },
  );
  const data = await r.json();

  res.setHeader('Cache-Control', 's-maxage=30, stale-while-revalidate=120');
  res.json(data.records.map(rec => ({
    featureId: rec.fields['Feature ID'],
    layer: rec.fields['_layerSlug'],
    status: rec.fields['Status'],
    qcResult: rec.fields['QC Result'],
  })));
}
```

- Airtable's rate limit is **5 requests/second per base**, shared by everyone. Ten field
  tablets polling directly will 429 each other. The `s-maxage` cache above collapses them
  into one upstream request.
- Ask for only the fields you paint with. Pulling every field on 4,000 records to color dots
  is 40× the payload for nothing.
- Filter server-side with `LAST_MODIFIED_TIME()` so a poll is a delta, not a full table.

---

## 7. Querying — what Airtable can and cannot answer

Airtable has no spatial index. It answers *attribute* questions well and *spatial* questions
not at all.

Fine in Airtable, straight from a view or `filterByFormula`:
- "Every embed on panel A-14 and its Δ"
- "All out-of-tolerance anchor bolts in Building A"
- "Everything shot on 2026-08-14 by the Tuesday crew"
- "Panels erected but not yet welded"
- "Storm runs with less than 3 ft of cover"

Not possible in Airtable:
- "Every point within 5 ft of gridline B"
- "Panels whose footprint intersects the crane path"
- "Nearest control point to this shot"

Options when you need those, in order of effort:
1. **Client-side with turf.js** — 4,000 features is nothing in memory. `turf.buffer` +
   `turf.booleanPointInPolygon` answers proximity in the browser. This covers most of it.
2. **Compute at import time** — the import script already knows the geometry; write the
   answer into a field (nearest gridline, distance to control) so Airtable can filter on it.
3. **PostGIS behind Airtable** — only when 1 and 2 stop being enough. Airtable stays the
   editing UI, Postgres becomes the query engine.

Do not reach for 3 on this project. A few thousand features is squarely option-1 territory.

---

## 8. Refresh cadence

| Change | What has to happen |
|---|---|
| Status / QC / panel progress edit | Nothing. Feature-state picks it up on the next poll. |
| New shots imported | Re-run the export + tiling. Minutes. |
| Point moved or voided | Re-run the export + tiling. |
| New layer added | New Layers row → re-export → `layers.json` updates the switcher. |
| Style tweak (color, width, dash) | Edit the Layers row → re-export `layers.json`. No re-tile. |

Wire the export to a nightly job plus a manual "publish" button. Log every run into
**Export Batches** so you can always answer which tileset the map is currently serving.
