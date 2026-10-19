import os
import unittest
from unittest.mock import patch

from crop_advisor.settings import load_settings


class SettingsTests(unittest.TestCase):
    def test_public_runtime_defaults_metrics_off_but_allows_private_opt_in(self) -> None:
        production_environment = {
            "CROP_ADVISOR_ENV": "production",
            "CROP_ADVISOR_ALLOWED_HOSTS": "api.example.test",
            "CROP_ADVISOR_MODEL_SHA256": "a" * 64,
        }
        with patch.dict(os.environ, production_environment, clear=True):
            self.assertFalse(load_settings().metrics_enabled)

        with patch.dict(
            os.environ,
            {**production_environment, "CROP_ADVISOR_METRICS_ENABLED": "true"},
            clear=True,
        ):
            self.assertTrue(load_settings().metrics_enabled)


if __name__ == "__main__":
    unittest.main()
