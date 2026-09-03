#!/usr/bin/env python3
"""Export Airtable features to per-layer GeoJSON plus a layers.json style manifest.

    export AIRTABLE_PAT=pat... AIRTABLE_BASE_ID=app...
    python scripts/airtable_to_geojson.py --out out/ --tileset you.henderson-survey

Writes:
    out/geojson/<layer-id>.geojson   one FeatureCollection per Layers row
    out/layers.json                  the layer registry the webapp consumes
    out/tippecanoe.sh                the exact tiling command for these layers

Feature IDs are promoted into the tile so the webapp can join live Airtable
attributes with setFeatureState without re-tiling.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _airtable import Client  # noqa: E402

# Kept deliberately small: everything here is baked into the tiles. Volatile
# attributes (status, QC, panel progress) are better delivered via feature-state.
POINT_PROPS = [
    "Feature ID", "Point Number", "Elevation", "Northing", "Easting",
    "Status", "QC Result", "Δ H (in)", "Δ Z", "Description", "Airtable Record ID",
]
LINE_PROPS = [
    "Feature ID", "Line Type", "Grid Label", "Length (ft)", "Status",
    "Utility Type", "Pipe Size (in)", "Pipe Material", "Invert Start", "Invert End",
    "Description", "Airtable Record ID",
]


def first_link(fields: dict, name: str):
    v = fields.get(name)
    return v[0] if isinstance(v, list) and v else None


def props(fields: dict, keys: list[str], extra: dict) -> dict:
    out = {k: fields[k] for k in keys if fields.get(k) not in (None, "", [])}
    out.update({k: v for k, v in extra.items() if v is not None})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("out"))
    ap.add_argument("--tileset", default="", help="mapbox tileset id, e.g. you.henderson-survey")
    ap.add_argument("--view", default="Map Export", help="Airtable view to export from")
    args = ap.parse_args()

    c = Client()

    layers = {}
    for r in c.list_records("Layers"):
        f = r["fields"]
        if f.get("Layer ID"):
            layers[r["id"]] = f

    buckets: dict[str, list[dict]] = {f["Layer ID"]: [] for f in layers.values()}
    orphans = {"points": 0, "lines": 0}
    skipped_geom = 0

    # --- points --------------------------------------------------------------
    panel_names = {r["id"]: r["fields"].get("Panel Mark") for r in c.list_records("Panels", fields=["Panel Mark"])}
    code_names = {r["id"]: r["fields"].get("Code") for r in c.list_records("Feature Codes", fields=["Code"])}

    for r in c.list_records("Point Features", view=args.view):
        f = r["fields"]
        lon, lat = f.get("Longitude"), f.get("Latitude")
        if lon is None or lat is None:
            skipped_geom += 1
            continue
        lid = layers.get(first_link(f, "Layer"), {}).get("Layer ID")
        if not lid:
            orphans["points"] += 1
            continue
        buckets[lid].append({
            "type": "Feature",
            "id": f.get("Feature ID"),
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props(f, POINT_PROPS, {
                "layer": lid,
                "panel": panel_names.get(first_link(f, "Panel")),
                "code": code_names.get(first_link(f, "Feature Code")),
            }),
        })

    # --- lines ---------------------------------------------------------------
    for r in c.list_records("Line Features", view=args.view):
        f = r["fields"]
        raw = f.get("Geometry GeoJSON")
        if not raw:
            skipped_geom += 1
            continue
        try:
            coords = json.loads(raw)
        except json.JSONDecodeError:
            print(f"  ! {f.get('Feature ID')}: Geometry GeoJSON is not valid JSON, skipped", file=sys.stderr)
            skipped_geom += 1
            continue
        if not isinstance(coords, list) or len(coords) < 2:
            skipped_geom += 1
            continue
        lid = layers.get(first_link(f, "Layer"), {}).get("Layer ID")
        if not lid:
            orphans["lines"] += 1
            continue
        buckets[lid].append({
            "type": "Feature",
            "id": f.get("Feature ID"),
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": props(f, LINE_PROPS, {
                "layer": lid,
                "panel": panel_names.get(first_link(f, "Panel")),
                "code": code_names.get(first_link(f, "Feature Code")),
            }),
        })

    # --- write ---------------------------------------------------------------
    gj_dir = args.out / "geojson"
    gj_dir.mkdir(parents=True, exist_ok=True)
    written = []
    total = 0
    for lid, feats in sorted(buckets.items()):
        if not feats:
            continue
        (gj_dir / f"{lid}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats})
        )
        written.append(lid)
        total += len(feats)
        print(f"  {lid:24s} {len(feats):5d}")

    manifest = []
    for f in sorted(layers.values(), key=lambda x: x.get("Draw Order", 0)):
        lid = f["Layer ID"]
        manifest.append({
            "id": lid,
            "name": f.get("Display Name", lid),
            "geometryType": f.get("Geometry Type"),
            "category": f.get("Category"),
            "discipline": f.get("Discipline"),
            "tileset": args.tileset or f.get("Tileset ID", ""),
            "sourceLayer": f.get("Source Layer") or lid,
            "minzoom": f.get("Min Zoom", 0),
            "maxzoom": f.get("Max Zoom", 22),
            "drawOrder": f.get("Draw Order", 0),
            "color": f.get("Color", "#666666"),
            "colorByStatus": bool(f.get("Color By Status")),
            "lineWidth": f.get("Line Width"),
            "lineDash": [float(x) for x in f["Line Dash"].split(",")] if f.get("Line Dash") else None,
            "circleRadius": f.get("Circle Radius"),
            "iconName": f.get("Icon Name"),
            "opacity": f.get("Opacity", 1),
            "visible": bool(f.get("Visible By Default")),
            "inSwitcher": bool(f.get("In Layer Switcher")),
            "clusterable": bool(f.get("Clusterable")),
            "labelField": f.get("Label Field"),
            "legendGroup": f.get("Legend Group"),
            "popupFields": json.loads(f["Popup Fields"]) if f.get("Popup Fields") else [],
            "featureCount": len(buckets.get(lid, [])),
            "hasData": lid in written,
        })
    (args.out / "layers.json").write_text(json.dumps(manifest, indent=2))

    cmd = ["tippecanoe", "-o", "tiles.mbtiles", "--force", "-Z10", "-z22",
           "--no-feature-limit", "--no-tile-size-limit", "--generate-ids"]
    for lid in written:
        cmd += ["-L", f"{lid}:geojson/{lid}.geojson"]
    script = "#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")\"\n\n" + " \\\n  ".join(cmd) + "\n"
    if args.tileset:
        script += (
            f"\n# upload\n"
            f"# mapbox upload {args.tileset} tiles.mbtiles\n"
        )
    sh = args.out / "tippecanoe.sh"
    sh.write_text(script)
    sh.chmod(0o755)

    print(f"\n{total} features across {len(written)} layers -> {args.out}")
    if orphans["points"] or orphans["lines"]:
        print(f"  ! unassigned Layer link: {orphans['points']} points, {orphans['lines']} lines "
              f"(these were dropped -- set Layer on them)")
    if skipped_geom:
        print(f"  ! {skipped_geom} records had no usable geometry (check the 'Missing Coordinates' view)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
