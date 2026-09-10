import json
import tempfile
import unittest
from pathlib import Path

import convert_tests


class ConverterTests(unittest.TestCase):
    def test_parse_steps_decodes_entities_and_heading_variants(self):
        source = (
            "Setup:<br>1. Install &ldquo;Keyman&rdquo;<br>"
            "Action Steps:<br>• Click the button<br>"
            "Cleanup Steps:<br>1. Close it<br>Trailing text"
        )

        self.assertEqual(
            convert_tests.parse_steps(source),
            {
                "setup": ['1. Install “Keyman”'],
                "action": ["• Click the button"],
                "cleanup": ["1. Close it", "Trailing text"],
                "unclassified": [],
            },
        )

    def test_assign_test_ids_adds_source_id_for_collisions(self):
        first = convert_tests.TestRecord("1", "Same test", "Windows", "", "", "", "", "", {}, "1.html", "1.JSON")
        second = convert_tests.TestRecord("2", "Same test", "Windows", "", "", "", "", "", {}, "2.html", "2.JSON")

        convert_tests.assign_test_ids([second, first])

        self.assertEqual(first.test_id, "TEST_SAME_TEST")
        self.assertEqual(second.test_id, "TEST_SAME_TEST_2")

    def test_convert_rejects_multiple_products_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "1.html").write_text("Action Steps:<br>Click it", encoding="utf-8")
            (root / "1.JSON").write_text(
                json.dumps(
                    {
                        "id": "1",
                        "name": "A test",
                        "attributes": {"Product": ["Web", "Android"]},
                    }
                ),
                encoding="utf-8",
            )

            report = convert_tests.convert(root, root / "markdown")

            self.assertEqual(report.pair_count, 1)
            self.assertTrue(any("expected exactly one Product" in error for error in report.errors))
            self.assertFalse((root / "markdown").exists())

    def test_convert_can_duplicate_multiple_product_records_when_opted_in(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "1.html").write_text("Action Steps:<br>Click it", encoding="utf-8")
            (root / "1.JSON").write_text(
                json.dumps(
                    {
                        "id": "1",
                        "name": "A test",
                        "attributes": {"Product": ["Web", "Android"]},
                    }
                ),
                encoding="utf-8",
            )

            report = convert_tests.convert(root, root / "markdown", allow_multiple_products=True)

            self.assertEqual(report.errors, [])
            self.assertEqual(report.product_counts, {"Android": 1, "Web": 1})
            self.assertTrue((root / "markdown" / "Android.md").exists())
            self.assertTrue((root / "markdown" / "Web.md").exists())

    def test_discover_pairs_ignores_project_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.JSON").write_text("{}", encoding="utf-8")
            (root / "1.html").write_text("", encoding="utf-8")
            (root / "1.JSON").write_text("{}", encoding="utf-8")
            report = convert_tests.ConversionReport()

            pairs = convert_tests.discover_pairs(root, report)

            self.assertEqual([pair[0] for pair in pairs], ["1"])
            self.assertEqual(report.errors, [])

    def test_render_record_collapses_metadata_and_shows_status_first(self):
        record = convert_tests.TestRecord(
            "1",
            "A test",
            "Windows",
            "Regression",
            "Manual",
            "Active",
            "",
            "",
            {"setup": [], "action": [], "cleanup": [], "unclassified": []},
            "1.html",
            "1.JSON",
            "TEST_A_TEST",
        )

        rendered = convert_tests.render_record(record)

        self.assertIn("**TEST_A_TEST**\nA test", rendered)
        self.assertIn("Status: `Active`", rendered)
        self.assertIn("<summary>Metadata</summary>", rendered)
        self.assertIn("- Source ID: `1`", rendered)
        self.assertNotIn("* **TEST_A_TEST:", rendered)
        self.assertNotIn("**TEST_A_TEST:**", rendered)
        self.assertNotIn("- Status:", rendered)
        self.assertNotIn("Execution level:", rendered)
        self.assertNotIn("Execution mode:", rendered)
        self.assertLess(rendered.index("Status:"), rendered.index("<summary>Metadata</summary>"))


if __name__ == "__main__":
    unittest.main()
