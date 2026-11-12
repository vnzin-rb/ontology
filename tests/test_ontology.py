import json
from pathlib import Path
import unittest

from ontology import validate


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


if __name__ == "__main__":
    unittest.main()
