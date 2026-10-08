"""Small HTTP client for a local Ollama server."""

from __future__ import annotations

import requests


class OllamaUnavailableError(RuntimeError):
    """Ollama could not be reached."""


class OllamaModelError(RuntimeError):
    """The configured model is unavailable in Ollama."""


def explain_repository(
    context: str,
    ollama_url: str,
    model: str,
    timeout_seconds: int = 300,
) -> str:
    """Ask the configured local model for a grounded, beginner-friendly explanation."""
    base_url = ollama_url.rstrip("/")
    prompt = f"""You are explaining a software repository to a beginner BCA student.
Use only the repository context below. Clearly label reasonable inferences, do not
invent features, and say when something cannot be determined from these files.
Explain the repository overview, technologies, important folders/files, application
flow, main components, and give a short simple-language summary. End with up to five
likely viva questions and concise answers based only on the supplied context.

Repository context:
{context}
"""
    try:
        health = requests.get(f"{base_url}/api/tags", timeout=10)
    except requests.RequestException as exc:
        raise OllamaUnavailableError(
            "Ollama is not running. Start Ollama and try again."
        ) from exc
    if not health.ok:
        raise OllamaUnavailableError("Ollama is not responding correctly. Start Ollama and retry.")

    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise OllamaUnavailableError(
            "Could not contact Ollama. Make sure it is running at the configured URL."
        ) from exc
    if response.status_code == 404:
        raise OllamaModelError(
            f"Ollama model '{model}' is unavailable. Pull or install this model locally."
        )
    if not response.ok:
        try:
            detail = response.json().get("error", "")
        except ValueError:
            detail = ""
        if "model" in str(detail).lower() and "not found" in str(detail).lower():
            raise OllamaModelError(
                f"Ollama model '{model}' is unavailable. Pull or install this model locally."
            )
        raise OllamaUnavailableError(f"Ollama request failed: {detail or response.reason}")
    try:
        explanation = response.json().get("response", "").strip()
    except (ValueError, AttributeError) as exc:
        raise OllamaUnavailableError("Ollama returned an invalid response.") from exc
    if not explanation:
        raise OllamaUnavailableError("Ollama returned an empty explanation.")
    return explanation
