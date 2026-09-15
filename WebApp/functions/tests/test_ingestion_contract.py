import unittest

from core.ingestion_contract import (
    IngestionContractError,
    build_canonical_delivery_point_index,
    determine_ingestion_outcome,
    get_classic_import_profile,
    validate_v2_job,
)


def make_job(**overrides):
    job = {
        "contract_version": "2.0",
        "status": "uploaded",
        "type": "FRUTTA",
        "tenantId": "DNR",
        "sourceChannel": "FRUTTA",
        "data_lavoro": "15-09-2026",
        "storage_path": "input_pdf_fornitore/file.pdf",
        "source": {
            "originalFilename": "file.pdf",
            "storagePath": "input_pdf_fornitore/file.pdf",
            "fileType": "application/pdf",
            "fileSize": 123,
        },
        "classification": {
            "mode": "CLASSIC",
            "operatorConfirmedSource": True,
            "ingestionProfileId": "dnr-frutta-ddt-pdf",
            "ingestionProfileVersion": 1,
        },
    }
    job.update(overrides)
    return job


class ClassicImportProfileTests(unittest.TestCase):
    def test_known_alias_is_normalized(self):
        profile = get_classic_import_profile("grand chef")
        self.assertEqual(profile.tenant_id, "GRAN CHEF")
        self.assertEqual(profile.source_channel, "ALTRO")

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(IngestionContractError):
            get_classic_import_profile("NUOVO_TENANT")


class IngestionOutcomeTests(unittest.TestCase):
    def test_zero_deliveries_is_a_failure(self):
        status, reasons = determine_ingestion_outcome(0)
        self.assertEqual(status, "failed_no_documents")
        self.assertEqual(reasons, ["NO_DOCUMENTS_EXTRACTED"])

    def test_clean_extraction_is_ready_for_certification(self):
        status, reasons = determine_ingestion_outcome(3)
        self.assertEqual(status, "ready_for_certification")
        self.assertEqual(reasons, [])

    def test_unknown_domain_data_requires_review(self):
        status, reasons = determine_ingestion_outcome(
            3,
            new_delivery_points=1,
            new_articles=2,
            new_time_windows=1,
        )
        self.assertEqual(status, "awaiting_domain_review")
        self.assertEqual(
            reasons,
            ["NEW_DELIVERY_POINTS", "NEW_ARTICLES", "NEW_TIME_WINDOWS"],
        )

    def test_skipped_pages_require_review(self):
        status, reasons = determine_ingestion_outcome(3, skipped_pages=1)
        self.assertEqual(status, "awaiting_domain_review")
        self.assertEqual(reasons, ["UNRECOGNIZED_PAGES"])


class CanonicalDeliveryPointIndexTests(unittest.TestCase):
    def test_indexes_only_the_requested_dnr_channel(self):
        points = [
            {"codice_esterno": "P10001", "sottocodice": "FRUTTA", "nome": "Bar Uno"},
            {"codice_esterno": "P10002", "sottocodice": "LATTE", "nome": "Bar Due"},
            {"codice_esterno": "P00000", "sottocodice": "FRUTTA", "nome": "Placeholder"},
        ]
        indexed = build_canonical_delivery_point_index(points, "FRUTTA")
        self.assertEqual(list(indexed), ["p10001"])
        self.assertEqual(indexed["p10001"]["nome"], "Bar Uno")

    def test_duplicate_code_in_same_channel_is_rejected(self):
        points = [
            {"codice_esterno": "P10001", "sottocodice": "FRUTTA"},
            {"codice_esterno": "p10001", "sottocodice": "FRUTTA"},
        ]
        with self.assertRaises(IngestionContractError):
            build_canonical_delivery_point_index(points, "FRUTTA")


class V2JobValidationTests(unittest.TestCase):
    def test_dnr_frutta_is_valid(self):
        profile = validate_v2_job(make_job(), "DNR")
        self.assertEqual(profile.profile_id, "dnr-frutta-ddt-pdf")

    def test_dnr_latte_is_valid(self):
        job = make_job(
            type="LATTE",
            sourceChannel="LATTE",
            classification={
                "mode": "CLASSIC",
                "operatorConfirmedSource": True,
                "ingestionProfileId": "dnr-latte-ddt-pdf",
                "ingestionProfileVersion": 1,
            },
        )
        self.assertEqual(validate_v2_job(job, "DNR").source_channel, "LATTE")

    def test_tenant_mismatch_is_rejected(self):
        with self.assertRaises(IngestionContractError):
            validate_v2_job(make_job(), "CATTEL")

    def test_missing_tenant_is_rejected(self):
        with self.assertRaises(IngestionContractError):
            validate_v2_job(make_job(tenantId=""), "DNR")

    def test_dnr_frutta_cannot_be_a_tenant(self):
        with self.assertRaises(IngestionContractError):
            validate_v2_job(make_job(tenantId="DNR_FRUTTA"), "DNR_FRUTTA")

    def test_invalid_channel_combination_is_rejected(self):
        with self.assertRaises(IngestionContractError):
            validate_v2_job(make_job(sourceChannel="ALTRO"), "DNR")

    def test_invalid_working_date_is_rejected(self):
        with self.assertRaises(IngestionContractError):
            validate_v2_job(make_job(data_lavoro="2026-09-15"), "DNR")

    def test_operator_confirmation_is_required(self):
        job = make_job()
        job["classification"] = dict(job["classification"], operatorConfirmedSource=False)
        with self.assertRaises(IngestionContractError):
            validate_v2_job(job, "DNR")

    def test_file_kind_must_match_profile(self):
        with self.assertRaises(IngestionContractError):
            validate_v2_job(make_job(is_excel=True), "DNR")

    def test_cattel_uses_explicit_altro_channel(self):
        job = make_job(
            type="CATTEL",
            tenantId="CATTEL",
            sourceChannel="ALTRO",
            is_excel=True,
            storage_path="input_pdf_fornitore/file.xlsx",
            source={
                "originalFilename": "file.xlsx",
                "storagePath": "input_pdf_fornitore/file.xlsx",
                "fileType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "fileSize": 123,
            },
            classification={
                "mode": "CLASSIC",
                "operatorConfirmedSource": True,
                "ingestionProfileId": "cattel-consegne-xlsx",
                "ingestionProfileVersion": 1,
            },
        )
        self.assertEqual(validate_v2_job(job, "CATTEL").source_channel, "ALTRO")


if __name__ == "__main__":
    unittest.main()
