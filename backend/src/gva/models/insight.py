from pydantic import BaseModel, Field


class ProjectInsight(BaseModel):
    name: str
    one_liner: str
    target_users: list[str] = Field(default_factory=list)
    problem: str
    core_features: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    architecture: str
    run_steps: list[str] = Field(default_factory=list)
    evidence: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Claim key to source file paths or snippets.",
    )
