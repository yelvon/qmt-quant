"""Extensible contract for historical point-in-time screening snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class SelectionRecord:
    code: str
    factors: Mapping[str, float | None] = field(default_factory=dict)
    reason: str = ""
    target_weight: float = 0.0


@dataclass(frozen=True)
class SelectionSnapshot:
    as_of_date: str
    records: Sequence[SelectionRecord]

    @property
    def codes(self) -> list[str]:
        return [record.code for record in self.records]

    def audit_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "as_of_date": self.as_of_date,
                "code": record.code,
                "factors": dict(record.factors),
                "reason": record.reason,
                "target_weight": record.target_weight,
            }
            for record in self.records
        ]


@runtime_checkable
class SelectionSnapshotProvider(Protocol):
    """Supply selections produced using only information available on ``date``."""

    def codes_as_of(self, date: str) -> Sequence[str]: ...

    def snapshot_as_of(self, date: str) -> SelectionSnapshot: ...


class RuleSelectionSnapshotProvider:
    """Evaluate the configured screening rule independently at every requested date."""

    def __init__(
        self,
        *,
        template_id: str = "low_pe",
        sector: str = "沪深A股",
        top_n: int = 30,
        exclude_st: bool = True,
    ) -> None:
        self.template_id = template_id
        self.sector = sector
        self.top_n = top_n
        self.exclude_st = exclude_st
        self._cache: dict[str, SelectionSnapshot] = {}

    def snapshot_as_of(self, date: str) -> SelectionSnapshot:
        as_of = str(date)[:10]
        if as_of not in self._cache:
            from qmt_quant.core.screener.runner import run_screening

            result = run_screening(
                template_id=self.template_id,
                sector=self.sector,
                top_n=self.top_n,
                exclude_st=self.exclude_st,
                as_of_date=as_of,
                persist=False,
            )
            records = [
                SelectionRecord(
                    code=str(row["code"]),
                    factors={
                        key: row.get(key)
                        for key in ("pe", "roe", "momentum_20d", "ma5", "ma20", "score")
                    },
                    reason=self.template_id,
                    target_weight=1.0 / max(len(result.get("results") or []), 1),
                )
                for row in result.get("results") or []
            ]
            self._cache[as_of] = SelectionSnapshot(as_of, records)
        return self._cache[as_of]

    def codes_as_of(self, date: str) -> Sequence[str]:
        return self.snapshot_as_of(date).codes
