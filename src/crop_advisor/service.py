"""Safe, model-agnostic recommendation service used by the HTTP layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd

from .contracts import DatasetContract
from .data import DataValidationError, prepare_inference_record, sha256_file


class ModelNotReadyError(RuntimeError):
    """Raised when the API starts before a trusted model artifact exists."""


class UnsupportedInputError(ValueError):
    """Raised when a categorical input falls outside the model's declared scope."""


@dataclass
class RecommendationService:
    """Validate inputs, rank model classes, and attach safety context."""

    pipeline: Any
    metadata: Mapping[str, Any]
    contract: DatasetContract

    @classmethod
    def from_artifact(
        cls,
        artifact_path: str | Path,
        contract: DatasetContract,
        expected_sha256: str | None = None,
    ) -> "RecommendationService":
        path = Path(artifact_path)
        if not path.exists():
            raise ModelNotReadyError(
                f"No trained model exists at {path}. Run the training command before serving requests."
            )
        if expected_sha256 is not None and sha256_file(path) != expected_sha256:
            raise ModelNotReadyError("The controlled model artifact failed its integrity check.")
        # joblib/pickle files are executable Python payloads. This service only
        # loads artifacts made by this repository in a controlled local build.
        try:
            bundle = joblib.load(path)
        except Exception as error:  # pragma: no cover - depends on corrupt local files
            raise ModelNotReadyError("The controlled model artifact could not be loaded.") from error
        if not isinstance(bundle, dict) or "pipeline" not in bundle or "metadata" not in bundle:
            raise ModelNotReadyError("The model artifact has an unexpected format.")
        pipeline = bundle["pipeline"]
        metadata = bundle["metadata"]
        required_metadata = {
            "feature_columns",
            "training_feature_metadata",
            "configuration",
            "model_format_version",
            "dataset_maturity",
        }
        try:
            classifier = pipeline.named_steps["classifier"]
            metadata_keys = set(metadata)
            is_valid = (
                callable(pipeline.predict_proba)
                and hasattr(classifier, "classes_")
                and required_metadata.issubset(metadata_keys)
            )
        except (AttributeError, KeyError, TypeError):
            is_valid = False
        if not is_valid:
            raise ModelNotReadyError("The controlled model artifact failed compatibility checks.")
        return cls(pipeline=pipeline, metadata=metadata, contract=contract)

    def _check_scope(self, record: Mapping[str, Any]) -> list[str]:
        feature_metadata = self.metadata["training_feature_metadata"]
        categorical_values = feature_metadata["categorical_values"]
        numeric_ranges = feature_metadata["numeric_ranges"]
        unsupported: list[str] = []
        warnings: list[str] = []

        for field, allowed_values in categorical_values.items():
            if record[field] not in allowed_values:
                supported = ", ".join(allowed_values)
                unsupported.append(f"{field} must be one of: {supported}.")
        if unsupported:
            raise UnsupportedInputError(" ".join(unsupported))

        for field, bounds in numeric_ranges.items():
            value = float(record[field])
            if value < bounds["minimum"] or value > bounds["maximum"]:
                warnings.append(
                    f"{field}={value:g} is outside the observed training range "
                    f"({bounds['minimum']:g}–{bounds['maximum']:g}); interpret this ranking cautiously."
                )
        return warnings

    def recommend(self, values: Mapping[str, Any], top_k: int | None = None) -> dict[str, Any]:
        """Return ordered candidates and limitations, never a false guarantee."""

        try:
            record = prepare_inference_record(values, self.contract)
        except DataValidationError:
            raise

        warnings = self._check_scope(record)
        feature_columns = list(self.metadata["feature_columns"])
        request_frame = pd.DataFrame([record], columns=feature_columns)
        probabilities = self.pipeline.predict_proba(request_frame)[0]
        classes = np.asarray(self.pipeline.named_steps["classifier"].classes_)
        requested_k = int(
            top_k or self.metadata["configuration"]["recommendation"]["top_k"]
        )
        k = min(max(requested_k, 1), len(classes))
        ranked_indexes = np.argsort(probabilities)[::-1][:k]
        candidates = [
            {"crop": str(classes[index]), "probability": round(float(probabilities[index]), 4)}
            for index in ranked_indexes
        ]
        highest_probability = float(probabilities[ranked_indexes[0]])
        threshold = float(
            self.metadata["configuration"]["recommendation"]["low_confidence_probability"]
        )
        if highest_probability < threshold:
            warnings.append(
                "The highest model probability is low. Consult a qualified local agronomist rather "
                "than using this ranking as a decision."
            )
        warnings.extend(
            [
                "This is a regional prototype trained only on the listed Maharashtra districts.",
                "It does not predict yield, profit, irrigation needs, fertiliser dosage, disease risk, or crop success.",
            ]
        )
        return {
            "best_suitable_crop": candidates[0]["crop"],
            "recommendations": candidates,
            "highest_probability": round(highest_probability, 4),
            "model_version": self.metadata["model_format_version"],
            "dataset_maturity": self.metadata["dataset_maturity"],
            "warnings": warnings,
        }
