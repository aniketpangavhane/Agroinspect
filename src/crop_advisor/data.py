"""Dataset validation, canonicalisation, and data-quality reporting.

This module is deliberately used by both training and serving.  That prevents
the common production failure where a model was trained on one interpretation
of a column but receives another at prediction time.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .contracts import ColumnSpec, DatasetContract, load_contract


class DataValidationError(ValueError):
    """Raised when a source dataset violates its declared contract."""


@dataclass
class ValidatedDataset:
    """The cleaned canonical dataframe plus an auditable quality report."""

    frame: pd.DataFrame
    contract: DatasetContract
    report: dict[str, Any]


def sha256_file(path: str | Path) -> str:
    """Return a content hash so a training run can name its exact input."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_manifest(data_path: str | Path, manifest_path: str | Path) -> dict[str, Any]:
    """Fail closed if the source file no longer matches its reviewed manifest.

    A hash is not proof that data is good; it is proof that the exact reviewed
    bytes are the ones reaching a training run.  Intentional source changes
    require a new manifest version and review instead of silently changing a
    model's foundation.
    """

    source_path = Path(data_path)
    metadata_path = Path(manifest_path)
    try:
        with metadata_path.open(encoding="utf-8") as source:
            manifest = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise DataValidationError(f"Could not read source manifest: {metadata_path}") from error

    expected_hash = str(manifest.get("sha256_at_intake", "")).lower()
    actual_hash = sha256_file(source_path)
    if len(expected_hash) != 64:
        raise DataValidationError(
            "Source manifest does not contain a valid sha256_at_intake value."
        )
    if actual_hash != expected_hash:
        raise DataValidationError(
            "Source file hash does not match the reviewed manifest. Create a new manifest version "
            "after reviewing an intentional data change; do not train on an unverified file."
        )
    return manifest


def _normalise_text(series: pd.Series, spec: ColumnSpec) -> pd.Series:
    """Apply the contract's safe, deterministic categorical cleanup rules."""

    text = series.astype("string")
    rules = spec.normalization or {}
    if rules.get("trim", False):
        text = text.str.strip()
    if rules.get("collapse_internal_whitespace", False):
        text = text.str.replace(r"\s+", " ", regex=True)
    return text


def _required_source_columns(contract: DatasetContract) -> set[str]:
    return {column.source_name for column in contract.columns if column.required}


def _categorical_summary(series: pd.Series) -> dict[str, Any]:
    counts = series.value_counts(dropna=False)
    summary: dict[str, Any] = {
        "distinct_values": int(series.nunique(dropna=True)),
    }
    # Keep reports useful without copying a long list of untrusted URLs or IDs
    # into every generated artifact.
    if len(counts) <= 50:
        summary["values"] = {str(value): int(count) for value, count in counts.items()}
    else:
        summary["top_values"] = {
            str(value): int(count) for value, count in counts.head(20).items()
        }
        summary["values_truncated"] = True
    return summary


def _numeric_summary(series: pd.Series) -> dict[str, float]:
    return {
        "minimum": float(series.min()),
        "maximum": float(series.max()),
        "mean": float(series.mean()),
        "median": float(series.median()),
    }


def _excluded_field_warnings(frame: pd.DataFrame, contract: DatasetContract) -> list[str]:
    """Surface obvious target leakage from fields declared as excluded."""

    target = contract.target.name
    warnings: list[str] = []
    for spec in contract.by_role("excluded"):
        mapping = frame.groupby(spec.name, dropna=False)[target].nunique(dropna=False)
        if not mapping.empty and bool((mapping <= 1).all()):
            warnings.append(
                f"Excluded column '{spec.name}' maps every observed value to one crop and "
                "would leak target information if it were used as a feature."
            )
        if spec.reason:
            warnings.append(f"Excluded column '{spec.name}': {spec.reason}")
    return warnings


def load_and_validate(
    data_path: str | Path,
    contract_path: str | Path,
    manifest_path: str | Path | None = None,
) -> ValidatedDataset:
    """Load a CSV, reject schema/range problems, and return canonical columns.

    The raw file is never changed.  For example, the source values ``"Red"``
    and ``"Red "`` become one canonical ``"Red"`` category in memory and in
    the generated curated dataset.
    """

    path = Path(data_path)
    contract = load_contract(contract_path)
    manifest = verify_source_manifest(path, manifest_path) if manifest_path else None
    raw = pd.read_csv(path)

    required = _required_source_columns(contract)
    missing_columns = sorted(required.difference(raw.columns))
    if missing_columns:
        raise DataValidationError(
            "Dataset is missing required source columns: " + ", ".join(missing_columns)
        )

    errors: list[str] = []
    normalized_changes: dict[str, int] = {}
    canonical: dict[str, pd.Series] = {}

    for spec in contract.columns:
        if spec.source_name not in raw.columns:
            # Optional columns are allowed to be absent. Required ones were
            # already handled above, so they cannot reach this branch.
            continue

        source_series = raw[spec.source_name]
        if spec.kind == "numeric":
            source_as_text = source_series.astype("string").str.strip()
            numeric = pd.to_numeric(source_series, errors="coerce")
            invalid = numeric.isna() & source_as_text.notna() & source_as_text.ne("")
            missing = numeric.isna()
            non_finite = ~np.isfinite(numeric.fillna(0))
            if bool(invalid.any()):
                errors.append(
                    f"{spec.source_name}: {int(invalid.sum())} non-numeric value(s)."
                )
            if spec.required and bool(missing.any()):
                errors.append(f"{spec.source_name}: {int(missing.sum())} missing value(s).")
            if bool(non_finite.any()):
                errors.append(f"{spec.source_name}: contains non-finite value(s).")
            if spec.minimum is not None:
                below_minimum = numeric < float(spec.minimum)
                if bool(below_minimum.any()):
                    errors.append(
                        f"{spec.source_name}: {int(below_minimum.sum())} value(s) below "
                        f"the minimum {spec.minimum}."
                    )
            if spec.maximum is not None:
                above_maximum = numeric > float(spec.maximum)
                if bool(above_maximum.any()):
                    errors.append(
                        f"{spec.source_name}: {int(above_maximum.sum())} value(s) above "
                        f"the maximum {spec.maximum}."
                    )
            canonical[spec.name] = numeric.astype(float)
        else:
            cleaned = _normalise_text(source_series, spec)
            original = source_series.astype("string")
            changed = int((cleaned.fillna("") != original.fillna("")).sum())
            normalized_changes[spec.name] = changed
            missing = cleaned.isna() | cleaned.eq("")
            if spec.required and bool(missing.any()):
                errors.append(f"{spec.source_name}: {int(missing.sum())} missing/blank value(s).")
            canonical[spec.name] = cleaned

    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise DataValidationError(f"Dataset failed validation:\n{formatted}")

    frame = pd.DataFrame(canonical)
    minimum_rows = int(contract.raw.get("quality_gates", {}).get("minimum_rows", 1))
    if len(frame) < minimum_rows:
        raise DataValidationError(
            f"Dataset has {len(frame)} rows; the contract requires at least {minimum_rows}."
        )

    feature_names = [column.name for column in contract.feature_columns()]
    target_name = contract.target.name
    target_counts = frame[target_name].value_counts().sort_index()
    low_count_threshold = int(
        contract.raw.get("quality_gates", {}).get("warn_if_target_class_count_below", 0)
    )
    sparse_classes = {
        str(label): int(count)
        for label, count in target_counts.items()
        if count < low_count_threshold
    }
    target_conflicts = (
        frame.groupby(feature_names, dropna=False)[target_name].nunique(dropna=False) > 1
    ).sum()

    warnings = list(contract.raw.get("quality_gates", {}).get("production_blockers", []))
    warnings.extend(_excluded_field_warnings(frame, contract))
    if sparse_classes:
        warnings.append(
            "Small target classes can make per-crop evaluation unstable: "
            + ", ".join(f"{label} ({count})" for label, count in sparse_classes.items())
            + "."
        )
    if contract.maturity != "production":
        warnings.append(
            f"Dataset maturity is '{contract.maturity}'; do not present model output as "
            "production-grade agricultural advice."
        )

    column_summaries: dict[str, Any] = {}
    for spec in contract.columns:
        if spec.name not in frame.columns:
            continue
        if spec.kind == "numeric":
            column_summaries[spec.name] = _numeric_summary(frame[spec.name])
        else:
            column_summaries[spec.name] = _categorical_summary(frame[spec.name])

    report: dict[str, Any] = {
        "contract_version": contract.version,
        "dataset_maturity": contract.maturity,
        "source_file": str(path),
        "source_sha256": sha256_file(path),
        "source_manifest": {
            "path": str(manifest_path),
            "manifest_version": manifest.get("manifest_version"),
            "status": manifest.get("status"),
        }
        if manifest
        else None,
        "row_count": int(len(frame)),
        "source_columns": list(raw.columns),
        "unexpected_source_columns": sorted(set(raw.columns).difference(contract.source_columns())),
        "normalized_value_changes": normalized_changes,
        "exact_duplicate_rows_after_cleaning": int(frame.duplicated().sum()),
        "duplicate_feature_rows": int(frame.duplicated(subset=feature_names).sum()),
        "conflicting_target_feature_vectors": int(target_conflicts),
        "target_distribution": {str(label): int(count) for label, count in target_counts.items()},
        "sparse_target_classes": sparse_classes,
        "columns": column_summaries,
        "warnings": warnings,
    }
    return ValidatedDataset(frame=frame, contract=contract, report=report)


def prepare_inference_record(
    values: Mapping[str, Any], contract: DatasetContract
) -> dict[str, Any]:
    """Validate one API record against feature-level contract rules.

    This deliberately checks broad physical/domain constraints only.  The
    serving layer adds a warning when a value falls outside the model's observed
    training range.
    """

    errors: list[str] = []
    clean: dict[str, Any] = {}
    for spec in contract.feature_columns():
        if spec.name not in values:
            errors.append(f"Missing required input '{spec.name}'.")
            continue
        value = values[spec.name]
        if spec.kind == "numeric":
            try:
                number = float(value)
            except (TypeError, ValueError):
                errors.append(f"'{spec.name}' must be numeric.")
                continue
            if not np.isfinite(number):
                errors.append(f"'{spec.name}' must be finite.")
                continue
            if spec.minimum is not None and number < float(spec.minimum):
                errors.append(f"'{spec.name}' must be at least {spec.minimum}.")
            if spec.maximum is not None and number > float(spec.maximum):
                errors.append(f"'{spec.name}' must be at most {spec.maximum}.")
            clean[spec.name] = number
        else:
            text = str(value)
            text = _normalise_text(pd.Series([text]), spec).iloc[0]
            if not text:
                errors.append(f"'{spec.name}' must not be blank.")
            clean[spec.name] = text
    if errors:
        raise DataValidationError(" ".join(errors))
    return clean


def write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    """Write an indented JSON report, creating only its requested directory."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")


def write_curated_csv(dataset: ValidatedDataset, path: str | Path) -> None:
    """Persist the canonical cleaned view without modifying the raw input."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dataset.frame.to_csv(destination, index=False)
