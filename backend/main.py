"""FastAPI entry point for GitHub Repository Code Explainer."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.models import ExplainRequest, ExplainResponse
from backend.groq_client import (
    GroqConfigurationError,
    GroqRateLimitError,
    GroqTimeoutError,
    GroqUnavailableError,
    explain_repository as explain_with_groq,
)
from backend.ollama_client import (
    OllamaModelError,
    OllamaUnavailableError,
    explain_repository,
)
from backend.services.repository_processor import analyze_repository, validate_github_url

load_dotenv()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "rafw007/qwen35-codex-coder:9b")
MAX_CONTEXT_CHARS = min(60_000, max(1_000, int(os.getenv("MAX_CONTEXT_CHARS", "60000"))))
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
# Render is the online deployment target and must always use Groq. Locally,
# LLM_PROVIDER can select Ollama (the local default) or Groq for development.
IS_RENDER = os.getenv("RENDER", "").strip().lower() == "true"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq" if IS_RENDER else "ollama").strip().lower()
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8501,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="GitHub Repository Code Explainer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def root() -> dict[str, str]:
    """Describe this API."""
    return {"message": "GitHub Repository Code Explainer API", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple API health status."""
    return {"status": "ok", "provider": active_provider()}


def active_provider() -> str:
    """Select Groq for all Render requests and configured provider locally."""
    if os.getenv("RENDER", "").strip().lower() == "true":
        return "groq"
    return os.getenv("LLM_PROVIDER", LLM_PROVIDER).strip().lower()


@app.post("/explain", response_model=ExplainResponse)
def explain(request: ExplainRequest) -> ExplainResponse:
    """Clone, read, and explain a public GitHub repository without executing it."""
    if not validate_github_url(request.repo_url):
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid public GitHub repository URL.",
        )
    provider = active_provider()
    if provider not in {"ollama", "groq"}:
        raise HTTPException(
            status_code=500,
            detail="LLM_PROVIDER must be either 'ollama' or 'groq'.",
        )
    if provider == "groq" and not os.getenv("GROQ_API_KEY", "").strip():
        raise HTTPException(
            status_code=503,
            detail="Groq mode is selected, but GROQ_API_KEY is not configured on the backend.",
        )
    try:
        result = analyze_repository(request.repo_url, MAX_CONTEXT_CHARS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result.files_analyzed:
        raise HTTPException(
            status_code=422,
            detail="No relevant readable source, configuration, or documentation files were found.",
        )
    try:
        if provider == "groq":
            explanation = explain_with_groq(
                result.context,
                os.getenv("GROQ_API_KEY"),
                os.getenv("GROQ_MODEL", GROQ_MODEL),
            )
        elif provider == "ollama":
            explanation = explain_repository(
                result.context,
                os.getenv("OLLAMA_URL", OLLAMA_URL),
                os.getenv("OLLAMA_MODEL", OLLAMA_MODEL),
            )
    except GroqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GroqRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except GroqTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except GroqUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaModelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ExplainResponse(
        repository=result.repository,
        files_analyzed=result.files_analyzed,
        explanation=explanation,
    )
