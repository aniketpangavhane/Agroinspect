from pathlib import Path
import unittest

import numpy as np

from crop_advisor.contracts import load_contract
from crop_advisor.service import RecommendationService, UnsupportedInputError


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "contracts" / "maharashtra_crop_recommendation.v1.json"


class FakeClassifier:
    classes_ = np.asarray(["Rice", "Wheat", "Sugarcane"])


class FakePipeline:
    named_steps = {"classifier": FakeClassifier()}

    def predict_proba(self, _frame):
        return np.asarray([[0.15, 0.25, 0.60]])


class RecommendationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        metadata = {
            "feature_columns": [
                "district",
                "soil_color",
                "nitrogen",
                "phosphorus",
                "potassium",
                "ph",
                "rainfall",
                "temperature",
            ],
            "training_feature_metadata": {
                "categorical_values": {
                    "district": ["Kolhapur"],
                    "soil_color": ["Black"],
                },
                "numeric_ranges": {
                    "nitrogen": {"minimum": 20, "maximum": 150},
                    "phosphorus": {"minimum": 10, "maximum": 90},
                    "potassium": {"minimum": 5, "maximum": 150},
                    "ph": {"minimum": 5.5, "maximum": 8.5},
                    "rainfall": {"minimum": 300, "maximum": 1700},
                    "temperature": {"minimum": 10, "maximum": 40},
                },
            },
            "configuration": {"recommendation": {"top_k": 3, "low_confidence_probability": 0.45}},
            "model_format_version": "1.0.0",
            "dataset_maturity": "prototype_unverified",
        }
        self.service = RecommendationService(
            pipeline=FakePipeline(), metadata=metadata, contract=load_contract(CONTRACT_PATH)
        )
        self.valid_values = {
            "district": "Kolhapur",
            "soil_color": "Black",
            "nitrogen": 75,
            "phosphorus": 50,
            "potassium": 100,
            "ph": 6.5,
            "rainfall": 1000,
            "temperature": 20,
        }

    def test_returns_ranked_candidates_and_warnings(self) -> None:
        response = self.service.recommend(self.valid_values)
        self.assertEqual(response["best_suitable_crop"], "Sugarcane")
        self.assertEqual(response["recommendations"][0]["crop"], "Sugarcane")
        self.assertEqual(len(response["recommendations"]), 3)
        self.assertTrue(any("regional prototype" in warning for warning in response["warnings"]))

    def test_rejects_unknown_scope_category(self) -> None:
        values = dict(self.valid_values, district="Unknown district")
        with self.assertRaises(UnsupportedInputError):
            self.service.recommend(values)


if __name__ == "__main__":
    unittest.main()
