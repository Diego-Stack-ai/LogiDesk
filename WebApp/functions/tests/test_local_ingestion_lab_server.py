import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from local_ingestion_lab_server import normalize_ingestion_context  # noqa: E402


class LocalIngestionLabContextTests(unittest.TestCase):
    def test_requires_explicit_tenant_without_dnr_fallback(self):
        with self.assertRaisesRegex(ValueError, "Committente obbligatorio"):
            normalize_ingestion_context({})

    def test_keeps_source_channel_optional(self):
        self.assertEqual(
            normalize_ingestion_context({"tenant_id": "CATTEL"}),
            ("CATTEL", None),
        )

    def test_accepts_tenant_specific_source_channel(self):
        self.assertEqual(
            normalize_ingestion_context(
                {"tenant_id": "CATTEL", "source_channel": "excel_cattel"}
            ),
            ("CATTEL", "EXCEL_CATTEL"),
        )

    def test_reads_legacy_channel_without_inventing_one(self):
        self.assertEqual(
            normalize_ingestion_context({"tenant_id": "DNR", "channel": "latte"}),
            ("DNR", "LATTE"),
        )


if __name__ == "__main__":
    unittest.main()
