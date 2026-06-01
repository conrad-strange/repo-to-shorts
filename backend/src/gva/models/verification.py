from typing import Literal

from pydantic import BaseModel, Field


class VerificationIssue(BaseModel):
    severity: Literal["low", "medium", "high"]
    claim: str
    reason: str
    suggestion: str


class VerificationReport(BaseModel):
    passed: bool
    issues: list[VerificationIssue] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
