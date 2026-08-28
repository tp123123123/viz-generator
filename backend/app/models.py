from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

JobStatus = Literal[
    "queued",
    "coding",
    "executing",
    "reviewing",
    "iterating",
    "succeeded",
    "failed",
]


class Issue(BaseModel):
    description: str
    severity: Literal["高", "中", "低"]
    suggestion: str


class ReviewResult(BaseModel):
    verdict: Literal["通过", "有条件通过", "不通过"]
    accuracy: float
    clarity: float
    aesthetics: float
    total: float
    passed: bool
    issues: list[Issue] = Field(default_factory=list)
    summary: str = ""
    next_advice: str = ""


class ExecutionResult(BaseModel):
    ok: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed_sec: float = 0
    image_path: str | None = None
    image_bytes: int = 0
    error: str | None = None


class VersionRecord(BaseModel):
    version: str
    iteration: int
    script_name: str
    image_name: str | None = None
    execution: ExecutionResult | None = None
    review: ReviewResult | None = None
    stage: str = ""


class JobState(BaseModel):
    id: str
    prompt: str
    csv_name: str = "data.csv"
    status: JobStatus = "queued"
    iteration: int = 0
    max_iterations: int = 3
    versions: list[VersionRecord] = Field(default_factory=list)
    stop_reason: str | None = None
    error: str | None = None
    current_version: str | None = None
    human_review: Literal["none", "awaiting", "accepted"] = "none"
    human_notes: list[str] = Field(default_factory=list)

    def to_public(self) -> dict[str, Any]:
        return self.model_dump()
