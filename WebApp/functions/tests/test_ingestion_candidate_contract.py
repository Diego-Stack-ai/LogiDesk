import unittest

from services.ingestion_candidate_contract import SCHEMA_VERSION, validate_candidate_bundle


class CandidateContractTests(unittest.TestCase):
    def test_accepts_explicit_read_only_bundle(self):
        bundle = {"schema_version": SCHEMA_VERSION, "producer": "LOCAL_AI", "context": {"tenant_id": "DNR", "source_file": "x.pdf", "source_page": 1},
                  "delivery_points": [], "travel_notes": [], "articles": [], "writes_performed": 0}
        self.assertIs(validate_candidate_bundle(bundle), bundle)

    def test_rejects_missing_tenant(self):
        bundle = {"schema_version": SCHEMA_VERSION, "producer": "LOCAL_AI", "context": {"source_file": "x.pdf", "source_page": 1},
                  "delivery_points": [], "travel_notes": [], "articles": [], "writes_performed": 0}
        with self.assertRaisesRegex(ValueError, "tenant_id"):
            validate_candidate_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
