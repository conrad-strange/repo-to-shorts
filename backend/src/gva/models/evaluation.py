from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluationIssue(BaseModel):
    severity: Literal["low", "medium", "high"]
    category: str
    message: str
    suggestion: str | None = None


class EvaluationReport(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    issues: list[EvaluationIssue] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    checked_files: list[Path] = Field(default_factory=list)
