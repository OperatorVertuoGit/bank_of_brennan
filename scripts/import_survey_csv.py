#!/usr/bin/env python3
"""Import surveyed points and lines from CSV into Airtable, transforming grid -> WGS84.

Point CSV (PNEZD, the default export from most data collectors):
    1001,25412.331,80233.118,1842.556,EMB P-14 north embed
    Point,Northing,Easting,Elevation,Description

Line CSV (one row per vertex, grouped and ordered by the first two columns):
    L-001,1,25412.331,80233.118,1842.556,PNL
    LineID,Seq,Northing,Easting,Elevation,Code

Before importing anything, check the transform against a point you already know:
    python scripts/import_survey_csv.py --check 25412.331 80233.118 --epsg 3421

Then:
    export AIRTABLE_PAT=pat... AIRTABLE_BASE_ID=app...
    python scripts/import_survey_csv.py points shots.csv --epsg 3421 \
        --area BLDG-A --session SS-2026-0142 --preview out/preview.geojson
    python scripts/import_survey_csv.py points shots.csv --epsg 3421 \
        --area BLDG-A --session SS-2026-0142 --commit
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    from pyproj import Transformer
except ImportError:
    Transformer = None


def transformer(epsg: int):
    if Transformer is None:
        sys.exit("pyproj is required: pip install -r requirements.txt")
    # always_xy: input and output are ordered (x, y) = (easting, northing) / (lon, lat)
    return Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)


def to_wgs84(tf, northing: float, easting: float) -> tuple[float, float]:
    lon, lat = tf.transform(easting, northing)
    return round(lon, 8), round(lat, 8)


def split_code(description: str) -> tuple[str, str]:
    """First whitespace-delimited token is the feature code; the rest is the note."""
    d = (description or "").strip()
    if not d:
        return "", ""
    parts = d.split(None, 1)
    return parts[0].upper(), (parts[1] if len(parts) > 1 else "")


def feature_id(prefix: str, area: str, key: int | str) -> str:
    """Stable, human-readable ID derived from the surveyor's own point/line key.

    Re-importing the same CSV must produce the same IDs, or the Mapbox promoteId
    join and every Airtable link breaks.
    """
    slug = (area or "SITE").upper().replace(" ", "-")
    if isinstance(key, int):
        return f"{prefix}-{slug}-{key:05d}"
    clean = re.sub(r"[^A-Za-z0-9]+", "-", str(key)).strip("-").upper()
    return f"{prefix}-{slug}-{clean}"


def read_points(path: pathlib.Path, tf, area: str) -> list[dict]:
    rows = []
    with path.open(newline="") as fh:
        for lineno, rec in enumerate(csv.reader(fh), start=1):
            if not rec or not rec[0].strip() or rec[0].strip().lower() in ("point", "p", "pt"):
                continue
            try:
                pnum = int(float(rec[0]))
                north, east, elev = float(rec[1]), float(rec[2]), float(rec[3])
            except (ValueError, IndexError):
                print(f"  ! line {lineno}: unparseable, skipped: {rec}", file=sys.stderr)
                continue
            desc = rec[4] if len(rec) > 4 else ""
            code, note = split_code(desc)
            lon, lat = to_wgs84(tf, north, east)
            rows.append({
                "Feature ID": feature_id("PT", area, pnum),
                "Point Number": pnum,
                "Northing": round(north, 3),
                "Easting": round(east, 3),
                "Elevation": round(elev, 3),
                "Longitude": lon,
                "Latitude": lat,
                "_code": code,
                "Description": note,
                "Geometry Source": "Field Shot",
                "Status": "As-Built",
                "Include in Tileset": True,
            })
    return rows


def read_lines(path: pathlib.Path, tf, area: str) -> list[dict]:
    groups: dict[str, list[tuple[int, float, float, float, str]]] = {}
    with path.open(newline="") as fh:
        for lineno, rec in enumerate(csv.reader(fh), start=1):
            if not rec or not rec[0].strip() or rec[0].strip().lower() in ("lineid", "line", "id"):
                continue
            try:
                lid = rec[0].strip()
                seq = int(float(rec[1]))
                north, east, elev = float(rec[2]), float(rec[3]), float(rec[4])
            except (ValueError, IndexError):
                print(f"  ! line {lineno}: unparseable, skipped: {rec}", file=sys.stderr)
                continue
            code = (rec[5].strip().upper() if len(rec) > 5 else "")
            groups.setdefault(lid, []).append((seq, north, east, elev, code))

    rows = []
    for lid, verts in sorted(groups.items()):
        verts.sort(key=lambda v: v[0])
        if len(verts) < 2:
            print(f"  ! line {lid}: only {len(verts)} vertex, skipped", file=sys.stderr)
            continue
        grid = [[round(v[1], 3), round(v[2], 3), round(v[3], 3)] for v in verts]
        wgs = [list(to_wgs84(tf, v[1], v[2])) for v in verts]
        length = sum(
            math.dist((a[0], a[1]), (b[0], b[1])) for a, b in zip(grid, grid[1:])
        )
        dn, de = grid[-1][0] - grid[0][0], grid[-1][1] - grid[0][1]
        run = math.hypot(dn, de)
        geo = json.dumps(wgs, separators=(",", ":"))
        if len(geo) > 90_000:
            print(f"  ! line {lid}: {len(geo)} chars exceeds the safe long-text budget; "
                  f"keep this geometry in the tile pipeline only", file=sys.stderr)
        rows.append({
            "Feature ID": feature_id("LN", area, lid),
            "Geometry GeoJSON": geo,
            "Vertex Coordinates (Grid)": json.dumps(grid, separators=(",", ":"))[:99_000],
            "Vertex Count": len(verts),
            "Length (ft)": round(length, 3),
            "Start N": grid[0][0], "Start E": grid[0][1], "Start Z": grid[0][2],
            "End N": grid[-1][0], "End E": grid[-1][1], "End Z": grid[-1][2],
            "Bearing": bearing_text(dn, de),
            "Grade %": round((grid[-1][2] - grid[0][2]) / run * 100, 3) if run else 0.0,
            "_code": verts[0][4],
            "Status": "As-Built",
            "Include in Tileset": True,
            "_source_id": lid,
        })
    return rows


def bearing_text(dn: float, de: float) -> str:
    """Quadrant bearing, the way it reads on a survey drawing."""
    if dn == 0 and de == 0:
        return ""
    ang = math.degrees(math.atan2(abs(de), abs(dn)))
    d = int(ang)
    m = int((ang - d) * 60)
    sec = round(((ang - d) * 60 - m) * 60)
    if sec == 60:
        sec, m = 0, m + 1
    if m == 60:
        m, d = 0, d + 1
    ns = "N" if dn >= 0 else "S"
    ew = "E" if de >= 0 else "W"
    return f"{ns} {d}°{m:02d}'{sec:02d}\" {ew}"


def write_preview(rows: list[dict], kind: str, path: pathlib.Path) -> None:
    feats = []
    for r in rows:
        if kind == "points":
            geom = {"type": "Point", "coordinates": [r["Longitude"], r["Latitude"]]}
        else:
            geom = {"type": "LineString", "coordinates": json.loads(r["Geometry GeoJSON"])}
        props = {k: v for k, v in r.items() if not k.startswith("_") and k != "Geometry GeoJSON"}
        props["code"] = r["_code"]
        feats.append({"type": "Feature", "id": r["Feature ID"], "geometry": geom, "properties": props})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"preview written: {path} ({len(feats)} features)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", nargs="?", choices=["points", "lines"])
    ap.add_argument("csv_path", nargs="?")
    ap.add_argument("--epsg", type=int, required=True,
                    help="source CRS, e.g. 3421 (NAD83 / Nevada East ftUS). Confirm with your surveyor.")
    ap.add_argument("--check", nargs=2, type=float, metavar=("NORTHING", "EASTING"),
                    help="transform one coordinate and exit -- do this before importing")
    ap.add_argument("--area", default="SITE", help="Area Code, used in the Feature ID")
    ap.add_argument("--project", help="Project Name to link")
    ap.add_argument("--session", help="Session ID to link")
    ap.add_argument("--preview", type=pathlib.Path, help="write a GeoJSON preview and stop")
    ap.add_argument("--commit", action="store_true", help="actually write to Airtable")
    args = ap.parse_args()

    tf = transformer(args.epsg)

    if args.check:
        n, e = args.check
        lon, lat = to_wgs84(tf, n, e)
        print(f"N {n} E {e}  (EPSG:{args.epsg})")
        print(f"  -> lon {lon}  lat {lat}")
        print(f"  -> https://www.google.com/maps?q={lat},{lon}")
        print("If that pin is not on your site, the EPSG code or the linear unit is wrong.")
        return 0

    if not args.kind or not args.csv_path:
        ap.error("kind and csv_path are required unless --check is used")

    path = pathlib.Path(args.csv_path)
    rows = read_points(path, tf, args.area) if args.kind == "points" else read_lines(path, tf, args.area)
    print(f"parsed {len(rows)} {args.kind}")

    if args.preview:
        write_preview(rows, args.kind, args.preview)
        if not args.commit:
            return 0

    if not args.commit:
        print("dry run -- pass --commit to write to Airtable")
        for r in rows[:3]:
            print("  ", {k: v for k, v in r.items() if k != "Vertex Coordinates (Grid)"})
        return 0

    from _airtable import Client
    c = Client()
    table = "Point Features" if args.kind == "points" else "Line Features"

    codes = c.index_by("Feature Codes", "Code")
    code_layer = {
        r["fields"]["Code"]: r["fields"].get("Layer", [None])[0]
        for r in c.list_records("Feature Codes", fields=["Code", "Layer"])
        if r["fields"].get("Code")
    }
    projects = c.index_by("Projects", "Project Name") if args.project else {}
    areas = c.index_by("Areas", "Area Code")
    sessions = c.index_by("Survey Sessions", "Session ID") if args.session else {}
    existing = c.index_by(table, "Feature ID")

    unknown: set[str] = set()
    payload = []
    for r in rows:
        f = {k: v for k, v in r.items() if not k.startswith("_")}
        code = r["_code"]
        if code and code in codes:
            f["Feature Code"] = [codes[code]]
            if code_layer.get(code):
                f["Layer"] = [code_layer[code]]
        elif code:
            unknown.add(code)
        if args.project and projects.get(args.project):
            f["Project"] = [projects[args.project]]
        if areas.get(args.area):
            f["Area"] = [areas[args.area]]
        if args.session and sessions.get(args.session):
            f["Survey Session"] = [sessions[args.session]]
        payload.append(f)

    if unknown:
        print(f"  ! codes not in Feature Codes, left unlinked: {sorted(unknown)}")

    creates = [f for f in payload if f["Feature ID"] not in existing]
    updates = [{"id": existing[f["Feature ID"]], "fields": f}
               for f in payload if f["Feature ID"] in existing]
    if creates:
        c.create_records(table, creates)
    if updates:
        c.update_records(table, updates)
    print(f"{table}: {len(creates)} created, {len(updates)} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
