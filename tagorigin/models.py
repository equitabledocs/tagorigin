"""tagorigin Pydantic models for output schema.

Defined here to avoid circular imports between signals and classify modules.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SignalResult(BaseModel):
    id: str
    description: str
    weight: float
    fired: bool
    evidence: str


class ProvenanceResult(BaseModel):
    file: str
    file_size_bytes: int
    file_md5: str
    classification: Literal[
        "UNTAGGED",
        "AUTO_TAGGED",
        "LIGHTLY_REMEDIATED",
        "REMEDIATED",
        "WELL_REMEDIATED",
    ]
    confidence: float = Field(..., ge=0.0, le=1.0)
    score: float
    signals: list[SignalResult]
    summary: str
    recommendation: str
    metadata: dict
