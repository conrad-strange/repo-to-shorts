from typing import Literal

from pydantic import BaseModel, Field


FileRole = Literal["readme", "config", "entry", "source", "test", "doc", "other"]


class RepoFile(BaseModel):
    path: str
    language: str | None = None
    role: FileRole
    excerpt: str = Field(description="A bounded excerpt used as evidence for downstream agents.")
    size: int


class RepoSummary(BaseModel):
    source: str
    repo_name: str
    default_branch: str | None = None
    files: list[RepoFile]
    tree_overview: str
    detected_stack: list[str] = Field(default_factory=list)
