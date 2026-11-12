"""Validate small ontologies represented as JSON."""

import argparse
from collections import deque
import json
from pathlib import Path
import re
import sys


IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


def identifier(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def collect_records(items, field, errors):
    if not isinstance(items, list):
        errors.append(f"{field}: expected an array")
        return {}

    records = {}
    for index, item in enumerate(items):
        path = f"{field}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{path}: expected an object")
            continue
        record_id = item.get("id")
        if not identifier(record_id):
            errors.append(f"{path}.id: expected a valid identifier")
            continue
        if record_id in records:
            errors.append(f"{path}.id: duplicate identifier {record_id!r}")
            continue
        records[record_id] = path, item
    return records


def validate(document):
    """Return a list of validation errors in document order."""
    if not isinstance(document, dict):
        return ["$: expected a JSON object"]

    errors = []
    classes = collect_records(document.get("classes"), "classes", errors)
    relations = collect_records(document.get("relations", []), "relations", errors)
    children = {class_id: [] for class_id in classes}
    indegree = dict.fromkeys(classes, 0)

    for class_id, (path, item) in classes.items():
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            errors.append(f"{path}.label: expected a non-empty string")
        parents = item.get("parents", [])
        if not isinstance(parents, list):
            errors.append(f"{path}.parents: expected an array")
            continue
        seen = set()
        for index, parent in enumerate(parents):
            parent_path = f"{path}.parents[{index}]"
            if not identifier(parent) or parent not in classes:
                errors.append(f"{parent_path}: unknown class")
            elif parent in seen:
                errors.append(f"{parent_path}: duplicate parent {parent!r}")
            else:
                seen.add(parent)
                indegree[class_id] += 1
                children[parent].append(class_id)

    pending = deque(class_id for class_id, count in indegree.items() if count == 0)
    visited = 0
    while pending:
        visited += 1
        for child in children[pending.popleft()]:
            indegree[child] -= 1
            if indegree[child] == 0:
                pending.append(child)
    if visited != len(classes):
        errors.append("classes: inheritance contains a cycle")

    for path, item in relations.values():
        for field in ("source", "target"):
            endpoint = item.get(field)
            if not identifier(endpoint) or endpoint not in classes:
                errors.append(f"{path}.{field}: unknown class")

    return errors


def read_and_validate(file):
    try:
        document = json.loads(file.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, [str(error)]
    return document, validate(document)


def validation_result(file, errors):
    return {"file": str(file), "valid": not errors, "errors": errors}


def print_validation(file, errors):
    if errors:
        for error in errors:
            print(f"{file}: {error}", file=sys.stderr)
    else:
        print(f"{file}: valid ontology")


def summarize(document):
    classes = document["classes"]
    return {
        "classes": len(classes),
        "relations": len(document.get("relations", [])),
        "roots": sorted(item["id"] for item in classes if not item.get("parents")),
    }


def ancestors(document, class_id):
    parents = {item["id"]: item.get("parents", []) for item in document["classes"]}
    if class_id not in parents:
        raise KeyError(class_id)
    found = set()
    pending = deque(parents[class_id])
    while pending:
        parent = pending.popleft()
        if parent not in found:
            found.add(parent)
            pending.extend(parents[parent])
    return sorted(found)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate_command = commands.add_parser("validate", help="validate an ontology")
    validate_command.add_argument("files", nargs="+", type=Path)
    validate_command.add_argument("--format", choices=("text", "json"), default="text")
    summary_command = commands.add_parser("summary", help="summarize a valid ontology")
    summary_command.add_argument("file", type=Path)
    ancestors_command = commands.add_parser("ancestors", help="list a class's ancestors")
    ancestors_command.add_argument("file", type=Path)
    ancestors_command.add_argument("class_id")
    args = parser.parse_args(argv)

    if args.command != "validate":
        document, errors = read_and_validate(args.file)
        if errors:
            print_validation(args.file, errors)
            return 1
        try:
            output = summarize(document) if args.command == "summary" else ancestors(document, args.class_id)
        except KeyError:
            print(f"{args.file}: unknown class {args.class_id!r}", file=sys.stderr)
            return 1
        print(json.dumps(output))
        return 0

    validations = [(file, read_and_validate(file)[1]) for file in args.files]
    if args.format == "json":
        payload = [validation_result(file, errors) for file, errors in validations]
        print(json.dumps(payload[0] if len(payload) == 1 else payload))
    else:
        for file, errors in validations:
            print_validation(file, errors)
    return int(any(errors for _, errors in validations))


if __name__ == "__main__":
    raise SystemExit(main())
