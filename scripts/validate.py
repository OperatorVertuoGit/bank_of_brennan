#!/usr/bin/env python3
"""Validate every record against its schema. Dependency-free JSON Schema subset.

  validate.py            validate everything under data/
  validate.py <file>     validate one file (schema inferred from its path)

Supports: type, required, properties, items, enum, pattern. Unknown keywords are
ignored on purpose — this is a guardrail, not a spec-complete validator.
"""
import json
import pathlib
import re
import sys

from _common import BUS, DATA, read_json

SCHEMAS = DATA / "schemas"

TYPES = {
    "object": dict, "array": list, "string": str, "number": (int, float),
    "integer": int, "boolean": bool, "null": type(None),
}


def _type_ok(value, spec):
    names = spec if isinstance(spec, list) else [spec]
    if isinstance(value, bool) and "boolean" not in names:
        return False
    return any(isinstance(value, TYPES[n]) for n in names if n in TYPES)


def validate(value, schema, path="$", errors=None):
    errors = [] if errors is None else errors
    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append(f"{path}: expected {schema['type']}, got {type(value).__name__}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(value, str):
        if not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match /{schema['pattern']}/")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required field {key!r}")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                validate(value[key], sub, f"{path}.{key}", errors)
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]", errors)
    return errors


def schema_for(path: pathlib.Path):
    p = str(path)
    if "/leads/_raw/" in p:
        return None  # untouched form dumps, not records
    if "/leads/" in p:
        return "lead"
    if "/quotes/" in p and path.suffix == ".json":
        return "quote"
    if "/invoices/" in p:
        return "invoice"
    if path.name == "job.json":
        return "job"
    if path.name == "qa-report.json":
        return "qa-report"
    if "/bus/" in p and path.suffix == ".json":
        return "message"
    return None


def main():
    targets = [pathlib.Path(a) for a in sys.argv[1:]]
    if not targets:
        targets = [p for p in DATA.rglob("*.json")
                   if SCHEMAS not in p.parents and (DATA / "registry") not in p.parents]
    failures = 0
    checked = 0
    for f in sorted(targets):
        kind = schema_for(f)
        if not kind:
            continue
        schema = read_json(SCHEMAS / f"{kind}.schema.json")
        try:
            doc = read_json(f)
        except json.JSONDecodeError as e:
            print(f"FAIL {f}\n  not valid JSON: {e}")
            failures += 1
            continue
        errs = validate(doc, schema)
        checked += 1
        if errs:
            failures += 1
            print(f"FAIL {f}  [{kind}]")
            for e in errs:
                print(f"  {e}")
    # Event log lines
    ev_schema = read_json(SCHEMAS / "event.schema.json")
    for f in sorted((BUS / "events").glob("*.jsonl")):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            checked += 1
            try:
                errs = validate(json.loads(line), ev_schema)
            except json.JSONDecodeError as e:
                errs = [f"not valid JSON: {e}"]
            if errs:
                failures += 1
                print(f"FAIL {f}:{n}")
                for e in errs:
                    print(f"  {e}")
    print(f"{checked} record(s) checked, {failures} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
