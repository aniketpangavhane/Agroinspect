from pathlib import Path
import unittest

from crop_advisor.contracts import load_contract
from crop_advisor.data import DataValidationError, load_and_validate, prepare_inference_record


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "contracts" / "maharashtra_crop_recommendation.v1.json"
DATA_PATH = ROOT / "Crop_recommendation.csv"
MANIFEST_PATH = ROOT / "data" / "metadata" / "maharashtra_crop_recommendation.v1.json"


class DataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract(CONTRACT_PATH)
        cls.dataset = load_and_validate(DATA_PATH, CONTRACT_PATH, MANIFEST_PATH)

    def test_contract_has_expected_model_boundary(self) -> None:
        self.assertEqual(self.contract.target.name, "crop")
        self.assertEqual(
            [column.name for column in self.contract.feature_columns()],
            [
                "district",
                "soil_color",
                "nitrogen",
                "phosphorus",
                "potassium",
                "ph",
                "rainfall",
                "temperature",
            ],
        )
        self.assertEqual(
            [column.name for column in self.contract.by_role("excluded")],
            ["fertilizer", "reference_link"],
        )

    def test_cleanup_normalizes_trailing_soil_color_space(self) -> None:
        colors = set(self.dataset.frame["soil_color"])
        self.assertIn("Red", colors)
        self.assertNotIn("Red ", colors)
        self.assertGreater(self.dataset.report["normalized_value_changes"]["soil_color"], 0)
        self.assertEqual(self.dataset.report["source_manifest"]["status"], "prototype_unverified")

    def test_prediction_record_has_contract_validation(self) -> None:
        record = prepare_inference_record(
            {
                "district": " Kolhapur ",
                "soil_color": " Black ",
                "nitrogen": 75,
                "phosphorus": 50,
                "potassium": 100,
                "ph": 6.5,
                "rainfall": 1000,
                "temperature": 20,
            },
            self.contract,
        )
        self.assertEqual(record["district"], "Kolhapur")
        self.assertEqual(record["soil_color"], "Black")
        with self.assertRaises(DataValidationError):
            prepare_inference_record({"ph": 15}, self.contract)


if __name__ == "__main__":
    unittest.main()
