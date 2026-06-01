from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    id: str
    source_path: str
    role: str
    excerpt: str
    derived_facts: list[str] = Field(default_factory=list)


class EvidenceIndex(BaseModel):
    repo_name: str
    items: list[EvidenceItem] = Field(default_factory=list)

    def resolve(self, refs: list[str]) -> list[EvidenceItem]:
        by_id = {item.id: item for item in self.items}
        resolved: list[EvidenceItem] = []
        for ref in refs:
            item = by_id.get(ref)
            if item is not None:
                resolved.append(item)
        return resolved


class ClaimCheck(BaseModel):
    id: str
    source: Literal["script", "storyboard", "visual"]
    text: str
    evidence_refs: list[str] = Field(default_factory=list)
    status: Literal["supported", "weak", "unsupported"]
    severity: Literal["low", "medium", "high"]
    reason: str


class VerificationReport(BaseModel):
    passed: bool
    claims: list[ClaimCheck] = Field(default_factory=list)
    metrics: dict[str, int | str | float | bool] = Field(default_factory=dict)


class RunInfo(BaseModel):
    run_id: str
    run_dir: Path
    root_output_dir: Path
