"""Reproducible training and evaluation for the regional prototype.

One sklearn Pipeline owns preprocessing and classification.  That is important:
the web service cannot accidentally apply a different scaler, category encoding,
or crop-ID mapping from the one used at training time.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, f1_score, recall_score
from sklearn.model_selection import LeaveOneGroupOut, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .contracts import DatasetContract
from .data import ValidatedDataset, load_and_validate, write_curated_csv, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "training.maharashtra.v1.json"


def _project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_training_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Read a declarative training-run configuration."""

    config_path = _project_path(path)
    with config_path.open(encoding="utf-8") as source:
        return json.load(source)


def _feature_names(contract: DatasetContract, kind: str | None = None) -> list[str]:
    return [
        column.name
        for column in contract.feature_columns()
        if kind is None or column.kind == kind
    ]


def build_pipeline(contract: DatasetContract, config: dict[str, Any]) -> Pipeline:
    """Build an unfitted preprocessing + classifier pipeline from the contract."""

    numeric_features = _feature_names(contract, "numeric")
    categorical_features = _feature_names(contract, "categorical")
    model_config = config["model"]

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))]),
                numeric_features,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("one_hot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    classifier = RandomForestClassifier(
        n_estimators=int(model_config["n_estimators"]),
        min_samples_leaf=int(model_config["min_samples_leaf"]),
        class_weight=model_config["class_weight"],
        n_jobs=int(model_config["n_jobs"]),
        random_state=int(config["random_seed"]),
    )
    return Pipeline(steps=[("preprocess", preprocessing), ("classifier", classifier)])


def _top_k_accuracy(
    probabilities: np.ndarray, classes: Iterable[str], truth: Iterable[str], top_k: int
) -> float:
    """Compute top-k accuracy even when a holdout contains unseen crop labels."""

    class_values = np.asarray(list(classes))
    if len(class_values) == 0:
        return 0.0
    k = min(top_k, len(class_values))
    ranking = np.argsort(probabilities, axis=1)[:, -k:]
    truth_values = np.asarray(list(truth))
    correct = [truth_values[index] in class_values[row] for index, row in enumerate(ranking)]
    return float(np.mean(correct)) if correct else 0.0


def _evaluate(
    pipeline: Pipeline, features: pd.DataFrame, target: pd.Series, top_k: int
) -> dict[str, Any]:
    """Return balanced classification metrics rather than accuracy alone."""

    predictions = pipeline.predict(features)
    probabilities = pipeline.predict_proba(features)
    classes = pipeline.named_steps["classifier"].classes_
    labels = sorted(set(target.astype(str)).union(set(map(str, predictions))))
    report = classification_report(
        target,
        predictions,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )
    return {
        "row_count": int(len(target)),
        "accuracy": float(accuracy_score(target, predictions)),
        # Balanced accuracy is macro recall. Supplying the labels observed in
        # this holdout also handles a district split whose model predicts a
        # crop class absent from that district without issuing a misleading
        # sklearn warning.
        "balanced_accuracy": float(
            recall_score(
                target,
                predictions,
                labels=sorted(set(target.astype(str))),
                average="macro",
                zero_division=0,
            )
        ),
        "macro_f1": float(f1_score(target, predictions, average="macro", zero_division=0)),
        f"top_{top_k}_accuracy": _top_k_accuracy(probabilities, classes, target, top_k),
        "per_crop": report,
    }


def _stratified_holdout(
    dataset: ValidatedDataset, config: dict[str, Any]
) -> dict[str, Any]:
    contract = dataset.contract
    feature_names = _feature_names(contract)
    target_name = contract.target.name
    frame = dataset.frame
    features = frame[feature_names]
    target = frame[target_name].astype(str)
    train_features, test_features, train_target, test_target = train_test_split(
        features,
        target,
        test_size=float(config["validation"]["test_size"]),
        random_state=int(config["random_seed"]),
        stratify=target,
    )
    pipeline = build_pipeline(contract, config)
    pipeline.fit(train_features, train_target)
    metrics = _evaluate(
        pipeline,
        test_features,
        test_target,
        int(config["recommendation"]["top_k"]),
    )
    return {
        "strategy": "stratified_random_holdout",
        "train_row_count": int(len(train_target)),
        "test_row_count": int(len(test_target)),
        "metrics": metrics,
        "warning": (
            "Rows from the same district can appear in both splits. This is a baseline only and "
            "may overstate performance for a new district."
        ),
    }


def _leave_one_group_out(
    dataset: ValidatedDataset, config: dict[str, Any]
) -> dict[str, Any]:
    """Measure the harder question: does a model transfer to another district?"""

    contract = dataset.contract
    group_column = contract.group_column
    feature_names = _feature_names(contract)
    target_name = contract.target.name
    frame = dataset.frame.reset_index(drop=True)
    features = frame[feature_names]
    target = frame[target_name].astype(str)
    groups = frame[group_column].astype(str)
    splitter = LeaveOneGroupOut()
    districts: dict[str, dict[str, Any]] = {}

    for train_index, test_index in splitter.split(features, target, groups):
        held_out = str(groups.iloc[test_index[0]])
        pipeline = build_pipeline(contract, config)
        pipeline.fit(features.iloc[train_index], target.iloc[train_index])
        evaluation = _evaluate(
            pipeline,
            features.iloc[test_index],
            target.iloc[test_index],
            int(config["recommendation"]["top_k"]),
        )
        train_crops = set(target.iloc[train_index])
        unseen_crops = sorted(set(target.iloc[test_index]).difference(train_crops))
        districts[held_out] = {
            "held_out_district": held_out,
            "unseen_test_crops": unseen_crops,
            "metrics": evaluation,
        }

    metric_name = "macro_f1"
    metric_values = [entry["metrics"][metric_name] for entry in districts.values()]
    return {
        "strategy": "leave_one_district_out",
        "district_count": int(len(districts)),
        "mean_macro_f1": float(np.mean(metric_values)) if metric_values else 0.0,
        "districts": districts,
        "warning": (
            "This is more realistic than a random row split, but only five districts are present. "
            "It is evidence for a prototype, not proof of statewide or field-level performance."
        ),
    }


def _training_feature_metadata(dataset: ValidatedDataset) -> dict[str, Any]:
    """Keep serving validation tied to the exact values seen by the final model."""

    metadata: dict[str, Any] = {"numeric_ranges": {}, "categorical_values": {}}
    for column in dataset.contract.feature_columns():
        series = dataset.frame[column.name]
        if column.kind == "numeric":
            metadata["numeric_ranges"][column.name] = {
                "minimum": float(series.min()),
                "maximum": float(series.max()),
            }
        else:
            metadata["categorical_values"][column.name] = sorted(
                str(value) for value in series.dropna().unique()
            )
    return metadata


def _model_card(metadata: dict[str, Any]) -> str:
    """Generate a compact model card alongside the model artifact."""

    primary = metadata["evaluation"]["stratified_random_holdout"]["metrics"]
    leave_one_out = metadata["evaluation"].get("leave_one_district_out")
    lines = [
        "# Model Card: Maharashtra Crop Suitability Prototype",
        "",
        "## Intended use",
        "",
        "Predict and rank the supplied recommended-crop labels for inputs from the five districts represented in the local prototype dataset. "
        "The labels are not independently verified agronomic outcomes; this is not a field-level, yield, profit, fertiliser, or safety guarantee.",
        "",
        "## Training data",
        "",
        f"- Dataset hash: `{metadata['source_sha256']}`",
        f"- Rows: {metadata['training_rows']}",
        f"- Contract version: {metadata['contract_version']}",
        f"- Features: {', '.join(metadata['feature_columns'])}",
        f"- Target meaning: {metadata['target_definition']}",
        f"- Excluded fields: {', '.join(metadata['excluded_columns'])}",
        "",
        "## Baseline evaluation",
        "",
        f"- Random stratified holdout accuracy: {primary['accuracy']:.3f}",
        f"- Random stratified holdout balanced accuracy: {primary['balanced_accuracy']:.3f}",
        f"- Random stratified holdout macro F1: {primary['macro_f1']:.3f}",
        f"- Random stratified holdout top-3 accuracy: {primary['top_3_accuracy']:.3f}",
    ]
    if leave_one_out:
        lines.extend(
            [
                "",
                "## District holdout",
                "",
                f"- Mean macro F1 when holding out one district: {leave_one_out['mean_macro_f1']:.3f}",
                "- Read the per-district metrics in `model_metadata.json`; crops absent from training for a held-out district cannot be learned by the classifier.",
            ]
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            *[f"- {warning}" for warning in metadata["data_quality_warnings"]],
            "",
            "Do not promote this artifact without agronomy review, verified data provenance, seasonal data, and outcome-based validation.",
            "",
        ]
    )
    return "\n".join(lines)


def train(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Validate data, evaluate honestly, fit a final model, and save one bundle."""

    config = deepcopy(load_training_config(config_path))
    dataset = load_and_validate(
        _project_path(config["data_path"]),
        _project_path(config["contract_path"]),
        _project_path(config["manifest_path"]),
    )
    artifact_dir = _project_path(config["artifact_dir"])
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # The curated view and its report are reproducible outputs. The raw CSV is
    # never overwritten by this command.
    write_curated_csv(dataset, _project_path(config["curated_data_path"]))
    write_json(artifact_dir / "data_quality_report.json", dataset.report)

    evaluations: dict[str, Any] = {
        "stratified_random_holdout": _stratified_holdout(dataset, config)
    }
    if bool(config["validation"].get("also_run_leave_one_district_out", False)):
        evaluations["leave_one_district_out"] = _leave_one_group_out(dataset, config)

    contract = dataset.contract
    feature_names = _feature_names(contract)
    target_name = contract.target.name
    final_pipeline = build_pipeline(contract, config)
    final_pipeline.fit(dataset.frame[feature_names], dataset.frame[target_name].astype(str))

    metadata: dict[str, Any] = {
        "model_format_version": "1.0.0",
        "run_name": config["run_name"],
        "contract_version": contract.version,
        "dataset_maturity": contract.maturity,
        "source_sha256": dataset.report["source_sha256"],
        "training_rows": int(len(dataset.frame)),
        "feature_columns": feature_names,
        "target_column": target_name,
        "target_definition": contract.raw["dataset"]["target_definition"],
        "excluded_columns": [column.name for column in contract.by_role("excluded")],
        "classes": sorted(str(value) for value in final_pipeline.named_steps["classifier"].classes_),
        "training_feature_metadata": _training_feature_metadata(dataset),
        "configuration": config,
        "evaluation": evaluations,
        "data_quality_warnings": dataset.report["warnings"],
    }
    bundle = {"pipeline": final_pipeline, "metadata": metadata}
    joblib.dump(bundle, artifact_dir / "model.joblib")
    write_json(artifact_dir / "model_metadata.json", metadata)
    (artifact_dir / "MODEL_CARD.md").write_text(_model_card(metadata), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the validated Crop Advisor prototype.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the declarative training JSON configuration.",
    )
    arguments = parser.parse_args()
    metadata = train(arguments.config)
    primary = metadata["evaluation"]["stratified_random_holdout"]["metrics"]
    print(f"Trained {metadata['run_name']} on {metadata['training_rows']} rows.")
    print(f"Artifact: {_project_path(metadata['configuration']['artifact_dir']) / 'model.joblib'}")
    print(f"Random-holdout macro F1: {primary['macro_f1']:.3f}")


if __name__ == "__main__":
    main()
