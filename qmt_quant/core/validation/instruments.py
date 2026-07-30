"""Instrument definitions for CN A-share."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Instrument:
    code: str
    name: str
    venue: str = "CN_A_SHARE"
    lot_size: int = 100


def is_st(name: str) -> bool:
    return "ST" in name.upper()


def from_code(code: str, name: str = "") -> Instrument:
    return Instrument(code=code, name=name or code)


def list_from_codes(codes: List[str]) -> List[Instrument]:
    return [from_code(c) for c in codes]
