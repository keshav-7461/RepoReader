"""Pydantic request and response models for the API."""

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    repo_url: str = Field(
        ...,
        max_length=512,
        description="HTTPS URL of a public GitHub repository",
    )


class ExplainResponse(BaseModel):
    repository: str
    files_analyzed: list[str]
    explanation: str
