"""Checks that every sample follows its schema, using only the 'jsonschema' library.

Run from the repo root:   python contracts\\check_contracts.py
Prints one line per contract and ends with "N contracts OK". Exits with an error if anything is wrong.
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
SCHEMAS = HERE / "schemas"
SAMPLES = HERE / "samples"


def main():
    schemas = {}
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        schemas[path.name[: -len(".schema.json")]] = json.loads(path.read_text(encoding="utf-8"))
    if not schemas:
        print("No schema files found in", SCHEMAS)
        return 1
    registry = Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in schemas.values()])

    problems = 0
    for name, schema in schemas.items():
        Draft202012Validator.check_schema(schema)
        sample_path = SAMPLES / (name + ".sample.json")
        if not sample_path.is_file():
            print("MISSING SAMPLE  ", name)
            problems += 1
            continue
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema, registry=registry).iter_errors(sample), key=lambda e: list(e.path))
        if errors:
            where = "/".join(str(p) for p in errors[0].path) or "(top level)"
            print("NOT VALID       ", name, "at", where, "-", errors[0].message)
            problems += 1
        else:
            print("ok              ", name)
    for path in sorted(SAMPLES.glob("*.sample.json")):
        if path.name[: -len(".sample.json")] not in schemas:
            print("SAMPLE WITHOUT SCHEMA", path.name)
            problems += 1
    if problems:
        print("%d problem(s) found" % problems)
        return 1
    print("%d contracts OK" % len(schemas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
