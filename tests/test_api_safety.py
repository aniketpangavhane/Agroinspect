import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from crop_advisor.api import app


class ApiSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_has_security_headers_and_request_id(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertTrue(response.headers["x-request-id"])

    def test_home_serves_the_prototype_form_with_content_security_policy(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="recommendation-form"', response.text)
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])

    def test_options_are_read_from_the_loaded_model_metadata(self) -> None:
        service = SimpleNamespace(
            metadata={
                "dataset_maturity": "prototype_unverified",
                "training_feature_metadata": {
                    "categorical_values": {
                        "district": ["Kolhapur", "Pune"],
                        "soil_color": ["Black", "Red"],
                    }
                },
            }
        )
        with patch("crop_advisor.api.get_service", return_value=service):
            response = self.client.get("/v1/options")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["districts"], ["Kolhapur", "Pune"])
        self.assertEqual(response.json()["soil_colors"], ["Black", "Red"])

    def test_rejects_non_finite_numbers_at_api_boundary(self) -> None:
        payload = (
            b'{"district":"Kolhapur","soil_color":"Black","nitrogen":Infinity,'
            b'"phosphorus":50,"potassium":100,"ph":6.5,"rainfall":1000,'
            b'"temperature":NaN}'
        )
        response = self.client.post(
            "/v1/recommendations",
            content=payload,
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_oversized_declared_request(self) -> None:
        response = self.client.post(
            "/v1/recommendations",
            content=b"{}",
            headers={"content-length": "65537", "content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 413)

    def test_rejects_unknown_host(self) -> None:
        response = self.client.get("/health", headers={"host": "untrusted.example"})
        self.assertEqual(response.status_code, 400)

    def test_metrics_can_be_disabled_for_public_hosting(self) -> None:
        from crop_advisor import api

        with patch.object(api, "SETTINGS", replace(api.SETTINGS, metrics_enabled=False)):
            response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
