import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ontology import ancestors, compare, descendants, export_dot, relations_for, summarize, validate


class OntologyTests(unittest.TestCase):
    def test_library_example(self):
        example = Path(__file__).resolve().parents[1] / "examples" / "library.json"
        self.assertEqual(validate(json.loads(example.read_text(encoding="utf-8"))), [])

    def test_unknown_endpoints_and_parents_report_field_paths(self):
        data = {
            "classes": [{"id": "Book", "label": "Book", "parents": [[]]}],
            "relations": [{"id": "writtenBy", "source": "Book", "target": "Author"}],
        }
        self.assertEqual(validate(data), [
            "classes[0].parents[0]: unknown class",
            "relations[0].target: unknown class",
        ])

    def test_inheritance_cycle(self):
        data = {"classes": [
            {"id": "A", "label": "A", "parents": ["B"]},
            {"id": "B", "label": "B", "parents": ["A"]},
        ]}
        self.assertEqual(validate(data), ["classes: inheritance contains a cycle"])

    def test_duplicate_class(self):
        data = {"classes": [{"id": "A", "label": "A"}, {"id": "A", "label": "A"}]}
        self.assertEqual(validate(data), ["classes[1].id: duplicate identifier 'A'"])


    def test_validation_json_is_machine_readable_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.json"
            source.write_text('{"classes": []', encoding="utf-8")
            run = subprocess.run(
                [sys.executable, "-B", "ontology.py", "validate", str(source), "--format", "json"],
                capture_output=True, text=True, check=False,
            )
        payload = json.loads(run.stdout)
        self.assertEqual(run.returncode, 1)
        self.assertFalse(payload["valid"])
        self.assertTrue(payload["errors"])
        self.assertEqual(run.stderr, "")

    def test_validation_accepts_multiple_files(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            run = subprocess.run(
                [sys.executable, "-B", "ontology.py", "validate",
                 "examples/library.json", str(missing), "--format", "json"],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(run.returncode, 1)
        self.assertEqual([item["valid"] for item in json.loads(run.stdout)], [True, False])

    def test_validation_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "duplicate.json"
            for contents, key in [
                ('{"classes": [], "classes": []}', "classes"),
                ('{"classes": [{"id": "A", "id": "B", "label": "B"}]}', "id"),
            ]:
                with self.subTest(key=key):
                    source.write_text(contents, encoding="utf-8")
                    run = subprocess.run(
                        [sys.executable, "-B", "ontology.py", "validate", str(source), "--format", "json"],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(run.returncode, 1)
                    self.assertEqual(json.loads(run.stdout)["errors"], [f"duplicate JSON key {key!r}"])

    def test_summary_lists_root_classes(self):
        data = {"classes": [
            {"id": "Child", "label": "Child", "parents": ["Root"]},
            {"id": "Root", "label": "Root"},
        ]}
        self.assertEqual(summarize(data), {"classes": 2, "relations": 0, "roots": ["Root"]})

    def test_ancestors_handles_shared_paths(self):
        data = {"classes": [
            {"id": "Root", "label": "Root"},
            {"id": "Left", "label": "Left", "parents": ["Root"]},
            {"id": "Right", "label": "Right", "parents": ["Root"]},
            {"id": "Leaf", "label": "Leaf", "parents": ["Left", "Right"]},
        ]}
        self.assertEqual(ancestors(data, "Leaf"), ["Left", "Right", "Root"])
        with self.assertRaises(KeyError):
            ancestors(data, "Missing")

    def test_descendants_are_sorted_and_unique(self):
        data = {"classes": [
            {"id": "Root", "label": "Root"},
            {"id": "Right", "label": "Right", "parents": ["Root"]},
            {"id": "Left", "label": "Left", "parents": ["Root"]},
            {"id": "Leaf", "label": "Leaf", "parents": ["Left", "Right"]},
        ]}
        self.assertEqual(descendants(data, "Root"), ["Leaf", "Left", "Right"])
        self.assertEqual(descendants(data, "Leaf"), [])
        with self.assertRaises(KeyError):
            descendants(data, "Missing")

    def test_dot_quotes_labels_and_includes_edges(self):
        data = {
            "classes": [
                {"id": "Book", "label": 'A "quoted" book', "parents": ["Resource"]},
                {"id": "Resource", "label": "Resource"},
            ],
            "relations": [{"id": "relatedTo", "source": "Book", "target": "Resource"}],
        }
        dot = export_dot(data)
        self.assertIn('[label=' + json.dumps(data["classes"][0]["label"]) + ']', dot)
        self.assertIn('"Book" -> "Resource" [label="is-a"];', dot)
        self.assertIn('"Book" -> "Resource" [label="relatedTo"];', dot)

    def test_instances_require_a_known_class(self):
        data = {
            "classes": [{"id": "Book", "label": "Book"}],
            "instances": [{"id": "sampleBook", "class": "Book"}],
        }
        self.assertEqual(validate(data), [])
        self.assertEqual(summarize(data)["instances"], 1)
        data["instances"][0]["class"] = "Missing"
        self.assertEqual(validate(data), ["instances[0].class: unknown class"])

    def test_diff_reports_ids_and_ignores_class_order(self):
        before = {"classes": [
            {"id": "Book", "label": "Livro"},
            {"id": "Author", "label": "Author"},
            {"id": "Old", "label": "Old"},
        ]}
        after = {"classes": [
            {"id": "Author", "label": "Author", "parents": []},
            {"id": "Book", "label": "Book"},
            {"id": "New", "label": "New"},
        ]}
        self.assertEqual(compare(before, after)["classes"], {
            "added": ["New"], "removed": ["Old"], "changed": ["Book"],
        })

    def test_relations_keeps_directions_separate(self):
        data = {
            "classes": [{"id": "Book", "label": "Book"}, {"id": "Author", "label": "Author"}],
            "relations": [
                {"id": "writtenBy", "source": "Book", "target": "Author"},
                {"id": "reviewed", "source": "Author", "target": "Book"},
            ],
        }
        self.assertEqual(relations_for(data, "Book"), {"incoming": ["reviewed"], "outgoing": ["writtenBy"]})

if __name__ == "__main__":
    unittest.main()
