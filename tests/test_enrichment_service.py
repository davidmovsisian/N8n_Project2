import json
import unittest
import uuid
from pathlib import Path

from src.enrichment_service import app


class EnrichmentServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_path = Path(__file__).parent / "fixtures" / "enrich_input_example.json"
        cls.sample_payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    def setUp(self):
        self.client = app.test_client()

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_categories(self):
        response = self.client.get("/categories")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("categories", body)
        self.assertIn("annual report on form 10-k", body["categories"])

    def test_sensitivity(self):
        response = self.client.post("/sensitivity", json=self.sample_payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"sensitivity": "internal"})

    def test_enrich(self):
        response = self.client.post("/enrich", json=self.sample_payload)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()

        metadata = body["metadata"]
        uuid.UUID(metadata["document_id"])
        self.assertEqual(metadata["department"], "Finance")
        self.assertEqual(metadata["sensitivity"], "internal")
        self.assertIn("auto-approved", metadata["routing_tags"])
        self.assertEqual(metadata["confidence_adjustment"], 0.2)


if __name__ == "__main__":
    unittest.main()
