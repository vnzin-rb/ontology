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
    instances = collect_records(document.get("instances", []), "instances", errors)
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

    for path, item in instances.values():
        class_id = item.get("class")
        if not identifier(class_id) or class_id not in classes:
            errors.append(f"{path}.class: unknown class")
        if "label" in item and (not isinstance(item["label"], str) or not item["label"].strip()):
            errors.append(f"{path}.label: expected a non-empty string")

    return errors


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def read_and_validate(file):
    try:
        document = json.loads(file.read_text(encoding="utf-8-sig"), object_pairs_hook=json_object)
    except (OSError, ValueError) as error:
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
        **({"instances": len(document["instances"])} if "instances" in document else {}),
        "roots": sorted(item["id"] for item in classes if not item.get("parents")),
    }


def ancestors(document, class_id):
    parents = {item["id"]: item.get("parents", []) for item in document["classes"]}
    return reachable_classes(parents, class_id)


def descendants(document, class_id):
    children = {item["id"]: [] for item in document["classes"]}
    for item in document["classes"]:
        for parent in item.get("parents", []):
            children[parent].append(item["id"])
    return reachable_classes(children, class_id)


def reachable_classes(edges, class_id):
    found = set()
    pending = deque(edges[class_id])
    while pending:
        neighbor = pending.popleft()
        if neighbor not in found:
            found.add(neighbor)
            pending.extend(edges[neighbor])
    return sorted(found)


def export_dot(document, include_instances=False):
    def quote(value):
        return json.dumps(value, ensure_ascii=False)

    lines = ["digraph ontology {"]
    for item in sorted(document["classes"], key=lambda record: record["id"]):
        class_id = quote(item["id"])
        lines.append(f"  {class_id} [label={quote(item['label'])}];")
        for parent in sorted(item.get("parents", [])):
            lines.append(f'  {class_id} -> {quote(parent)} [label="is-a"];')
    for relation in sorted(document.get("relations", []), key=lambda record: record["id"]):
        lines.append(f"  {quote(relation['source'])} -> {quote(relation['target'])} [label={quote(relation['id'])}];")
    if include_instances:
        for instance in sorted(document.get("instances", []), key=lambda record: record["id"]):
            node = quote(f"instance:{instance['id']}")
            label = quote(instance.get("label", instance["id"]))
            lines.append(f"  {node} [label={label}, shape=box];")
            lines.append(f'  {node} -> {quote(instance["class"])} [label="instance-of"];')
    lines.append("}")
    return "\n".join(lines)


def compare(left, right):
    def index(document, kind):
        records = {}
        for item in document.get(kind, []):
            if kind == "classes":
                item = {**item, "parents": sorted(item.get("parents", []))}
            records[item["id"]] = item
        return records

    output = {}
    for kind in ("classes", "relations", "instances"):
        before = index(left, kind)
        after = index(right, kind)
        output[kind] = {
            "added": sorted(after.keys() - before.keys()),
            "removed": sorted(before.keys() - after.keys()),
            "changed": sorted(key for key in before.keys() & after.keys() if before[key] != after[key]),
        }
    return output


def relations_for(document, class_id):
    if not any(item["id"] == class_id for item in document["classes"]):
        raise KeyError(class_id)
    relations = document.get("relations", [])
    return {
        "incoming": sorted(item["id"] for item in relations if item["target"] == class_id),
        "outgoing": sorted(item["id"] for item in relations if item["source"] == class_id),
    }


def instances_for(document, class_id, include_descendants=False):
    if not any(item["id"] == class_id for item in document["classes"]):
        raise KeyError(class_id)
    class_ids = {class_id}
    if include_descendants:
        class_ids.update(descendants(document, class_id))
    return sorted(item["id"] for item in document.get("instances", []) if item["class"] in class_ids)


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
    descendants_command = commands.add_parser("descendants", help="list a class's descendants")
    descendants_command.add_argument("file", type=Path)
    descendants_command.add_argument("class_id")
    relations_command = commands.add_parser("relations", help="list a class's incoming and outgoing relations")
    relations_command.add_argument("file", type=Path)
    relations_command.add_argument("class_id")
    instances_command = commands.add_parser("instances", help="list a class's instances")
    instances_command.add_argument("file", type=Path)
    instances_command.add_argument("class_id")
    instances_command.add_argument("--include-descendants", action="store_true")
    dot_command = commands.add_parser("export-dot", help="export the class graph as DOT")
    dot_command.add_argument("file", type=Path)
    dot_command.add_argument("--include-instances", action="store_true", help="include instances as nodes")
    dot_command.add_argument("-o", "--output", type=Path, help="write the graph to a UTF-8 file")
    diff_command = commands.add_parser("diff", help="compare two valid ontologies")
    diff_command.add_argument("before", type=Path)
    diff_command.add_argument("after", type=Path)
    args = parser.parse_args(argv)

    if args.command == "diff":
        before, before_errors = read_and_validate(args.before)
        after, after_errors = read_and_validate(args.after)
        if before_errors or after_errors:
            if before_errors:
                print_validation(args.before, before_errors)
            if after_errors:
                print_validation(args.after, after_errors)
            return 1
        print(json.dumps(compare(before, after)))
        return 0

    if args.command != "validate":
        document, errors = read_and_validate(args.file)
        if errors:
            print_validation(args.file, errors)
            return 1
        if args.command == "export-dot":
            graph = export_dot(document, args.include_instances)
            if args.output is None:
                print(graph)
                return 0
            try:
                args.output.write_text(graph + "\n", encoding="utf-8")
            except (OSError, UnicodeError) as error:
                print(f"{args.output}: {error}", file=sys.stderr)
                return 1
            return 0
        if args.command == "summary":
            print(json.dumps(summarize(document)))
            return 0
        lookups = {"ancestors": ancestors, "descendants": descendants, "relations": relations_for}
        try:
            if args.command == "instances":
                output = instances_for(document, args.class_id, args.include_descendants)
            else:
                output = lookups[args.command](document, args.class_id)
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
