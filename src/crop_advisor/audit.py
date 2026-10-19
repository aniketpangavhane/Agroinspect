"""Command-line data-quality audit without fitting a model."""

from __future__ import annotations

import argparse
from pathlib import Path

from .data import load_and_validate, write_curated_csv, write_json
from .training import DEFAULT_CONFIG_PATH, _project_path, load_training_config


def audit(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    """Create a cleaned canonical CSV and a machine-readable quality report."""

    config = load_training_config(config_path)
    dataset = load_and_validate(
        _project_path(config["data_path"]),
        _project_path(config["contract_path"]),
        _project_path(config["manifest_path"]),
    )
    artifact_dir = _project_path(config["artifact_dir"])
    write_curated_csv(dataset, _project_path(config["curated_data_path"]))
    write_json(artifact_dir / "data_quality_report.json", dataset.report)
    return dataset.report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and profile Crop Advisor data.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    arguments = parser.parse_args()
    report = audit(arguments.config)
    print(f"Validated {report['row_count']} rows.")
    print(f"Curated data: {_project_path(load_training_config(arguments.config)['curated_data_path'])}")
    print(f"Warnings: {len(report['warnings'])}")


if __name__ == "__main__":
    main()
