import unittest
from unittest.mock import MagicMock
import os
import json
import shutil
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from scripts.migrations.core_v1.m2_vehicles_write import M2VehiclesWrite

class TestM2VehiclesWrite(unittest.TestCase):
    def setUp(self):
        self.output_dir = "migration_output/tests_m2_write"
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_preflight_clean_start(self):
        db_mock = MagicMock()
        args = MagicMock()
        args.project = "log-solutions-cantiere"
        args.company_id = "NzXaCgyXxZWWehw1tSlo"
        args.execute = False
        args.confirm_shadow_write = None
        args.output_dir = self.output_dir

        mig = M2VehiclesWrite(db_mock, args)
        mig.legacy_data = [{"legacy_document_id": f"v{i}", "legacy_data": {"targa": f"A{i}B", "attivo": True}} for i in range(24)]
        mig.legacy_data.append({"legacy_document_id": "_patenti", "legacy_data": {}})
        mig.legacy_data.append({"legacy_document_id": "_tipologie", "legacy_data": {}})

        mig.gates["GATE_M0_M1_COMPLETE"] = True
        mig.gates["GATE_SOURCE_COUNT_26"] = True

        mig.classify_source_documents()
        mig.state_classification = "CLEAN_START"
        mig.gates["GATE_PRE_STATE_CLEAN"] = True

        mig.transform_vehicles()
        mig.build_write_plan()
        mig.validate_plan()

        self.assertEqual(len(mig.write_plan), 25)
        self.assertTrue(mig.gates["GATE_ATOMIC_PLAN_VALID"])

        # Test preview IDs
        self.assertTrue(all(v["vehicle_id"].startswith("PREVIEW::") for v in mig.registry_payload["vehicle_mapping"].values()))

    def test_unknown_field_stops_execution(self):
        db_mock = MagicMock()
        args = MagicMock()
        args.project = "log-solutions-cantiere"
        args.company_id = "NzXaCgyXxZWWehw1tSlo"
        args.execute = False
        args.output_dir = self.output_dir

        mig = M2VehiclesWrite(db_mock, args)
        mig.real_vehicles = [{"legacy_document_id": "v1", "legacy_data": {"targa": "A1B", "attivo": True, "unknown_field_xyz": 123}}]

        with self.assertRaises(SystemExit):
            mig.transform_vehicles()

    def test_storage_field_halts_execution(self):
        db_mock = MagicMock()
        args = MagicMock()
        args.project = "log-solutions-cantiere"
        args.company_id = "NzXaCgyXxZWWehw1tSlo"
        args.execute = False
        args.output_dir = self.output_dir

        mig = M2VehiclesWrite(db_mock, args)
        mig.real_vehicles = [{"legacy_document_id": "v1", "legacy_data": {"targa": "A1B", "attivo": True, "fotoUrls": ["http://test"]}}]

        # Wait, the script allows storage fields in source, it just excludes them from canonical payload.
        # But if for some reason they leak into canonical_payload, it stops. We need to check if the script excludes them correctly.
        # Actually my script explicitly checks `if f in deferred_storage: if f in canonical_payload: sys.exit(1)`.
        # So we expect it to NOT sys.exit(1), because `transform_vehicles` strips them out.
        mig.transform_vehicles()
        self.assertTrue(mig.gates["GATE_STORAGE_WRITE_ZERO"])
        self.assertNotIn("fotoUrls", mig.write_plan[0]["payload"])

if __name__ == '__main__':
    unittest.main()
