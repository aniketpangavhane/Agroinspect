"""Read the declarative dataset contract used by every pipeline stage.

Keeping column meaning in JSON rather than scattering it through Python makes a
source-schema change visible and reviewable before a model is retrained.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ColumnSpec:
    """One source-to-canonical column definition from the dataset contract."""

    source_name: str
    name: str
    role: str
    kind: str
    required: bool
    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None
    reason: str | None = None
    normalization: dict[str, Any] | None = None


@dataclass(frozen=True)
class DatasetContract:
    """Validated, convenient representation of the JSON contract."""

    raw: dict[str, Any]
    columns: tuple[ColumnSpec, ...]

    @property
    def version(self) -> str:
        return str(self.raw["contract_version"])

    @property
    def target(self) -> ColumnSpec:
        targets = self.by_role("target")
        if len(targets) != 1:
            raise ValueError("The data contract must define exactly one target column.")
        return targets[0]

    @property
    def group_column(self) -> str:
        return str(self.raw["dataset"]["group_column"])

    @property
    def maturity(self) -> str:
        return str(self.raw["dataset"].get("maturity", "unknown"))

    def by_role(self, role: str) -> tuple[ColumnSpec, ...]:
        return tuple(column for column in self.columns if column.role == role)

    def feature_columns(self) -> tuple[ColumnSpec, ...]:
        return self.by_role("feature")

    def source_columns(self) -> tuple[str, ...]:
        return tuple(column.source_name for column in self.columns)

    def canonical_columns(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    def column(self, canonical_name: str) -> ColumnSpec:
        for candidate in self.columns:
            if candidate.name == canonical_name:
                return candidate
        raise KeyError(f"{canonical_name!r} is not declared in the dataset contract.")


def load_contract(path: str | Path) -> DatasetContract:
    """Load and sanity-check a JSON data contract."""

    contract_path = Path(path)
    with contract_path.open(encoding="utf-8") as source:
        raw = json.load(source)

    if "contract_version" not in raw or "columns" not in raw or "dataset" not in raw:
        raise ValueError(f"{contract_path} is not a valid Crop Advisor data contract.")

    columns = tuple(
        ColumnSpec(
            source_name=item["source_name"],
            name=item["name"],
            role=item["role"],
            kind=item["kind"],
            required=bool(item.get("required", False)),
            minimum=item.get("minimum"),
            maximum=item.get("maximum"),
            unit=item.get("unit"),
            reason=item.get("reason"),
            normalization=item.get("normalization"),
        )
        for item in raw["columns"]
    )

    source_names = [column.source_name for column in columns]
    canonical_names = [column.name for column in columns]
    if len(source_names) != len(set(source_names)):
        raise ValueError("The data contract has duplicate source column names.")
    if len(canonical_names) != len(set(canonical_names)):
        raise ValueError("The data contract has duplicate canonical column names.")

    contract = DatasetContract(raw=raw, columns=columns)
    # Accessing this property performs the one-target validation early.
    _ = contract.target
    return contract
