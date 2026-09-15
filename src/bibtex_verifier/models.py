from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    VERIFIED = "verified"
    SUGGESTED_UPDATES = "suggested_updates"
    NEEDS_REVIEW = "needs_review"
    UNRESOLVED = "unresolved"
    CONFLICT = "conflict"


class Publication(BaseModel):
    model_config = ConfigDict(extra="allow")

    citation_key: str = ""
    entry_type: str = "misc"
    title: str = ""
    author: str = ""
    year: str = ""
    journal: str = ""
    booktitle: str = ""
    volume: str = ""
    number: str = ""
    pages: str = ""
    doi: str = ""
    publisher: str = ""
    url: str = ""
    source: str = ""


class Evidence(BaseModel):
    confidence: int = Field(ge=0, le=100)
    decision: str
    reasons: list[str]
    signals: dict[str, str | int | float | None]


class FieldDifference(BaseModel):
    field: str
    original: str
    suggested: str
    score: float
    source: str = ""


class VerificationResult(BaseModel):
    citation_key: str
    title: str
    status: Status
    confidence: int | None = None
    evidence: Evidence | None = None
    sources: list[str] = Field(default_factory=list)
    matched: Publication | None = None
    field_differences: list[FieldDifference] = Field(default_factory=list)


class VerificationReport(BaseModel):
    schema_version: str = "1.0"
    tool_version: str
    generated_at: str
    input_sha256: str
    summary: dict[str, int]
    warnings: list[str] = Field(default_factory=list)
    entries: list[VerificationResult]
