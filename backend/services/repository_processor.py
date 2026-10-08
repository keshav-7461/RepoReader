"""Clone public GitHub repositories and select useful text files safely."""

from __future__ import annotations

import re
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from git import GitCommandError, Repo


SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp", ".h",
    ".hpp", ".cs", ".go", ".rs", ".php", ".rb", ".swift", ".kt",
    ".html", ".css", ".scss", ".sql", ".sh", ".yaml", ".yml", ".json",
    ".toml", ".md",
}
SOURCE_EXTENSIONS = SUPPORTED_EXTENSIONS - {
    ".html", ".css", ".scss", ".sql", ".yaml", ".yml", ".json", ".toml", ".md",
}
IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "coverage", ".idea", ".vscode",
}
PRIORITY_NAMES = {
    "readme.md": 0, "package.json": 1, "requirements.txt": 2,
    "pyproject.toml": 3, "setup.py": 4, "main.py": 5, "app.py": 6,
    "server.py": 7, "index.py": 8, "index.js": 9, "index.ts": 10,
}
GENERATED_PARTS = (".min.", ".generated.", ".g.", "_pb2.py", ".lock")
LOCK_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "cargo.lock", "pipfile.lock", "composer.lock", "gemfile.lock",
}
MAX_FILE_CHARS = 20_000


@dataclass
class RepositoryContext:
    """Selected files and their bounded text context."""

    repository: str
    files_analyzed: list[str]
    context: str


def validate_github_url(repo_url: str) -> bool:
    """Accept only HTTPS URLs pointing to a GitHub owner/repository path."""
    try:
        parsed = urlparse(repo_url.strip())
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        return (
            parsed.scheme == "https"
            and parsed.hostname == "github.com"
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and len(parts) == 2
            and all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts)
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def _rank_file(path: Path, root: Path) -> tuple[int, int, int, str]:
    relative = path.relative_to(root).as_posix()
    name = path.name.lower()
    if name in PRIORITY_NAMES:
        return (0, PRIORITY_NAMES[name], 0, relative.lower())
    parts = {part.lower() for part in path.relative_to(root).parts[:-1]}
    if parts.intersection({"src", "backend", "frontend"}):
        return (1, 0, len(path.parts), relative.lower())
    if path.suffix.lower() in SOURCE_EXTENSIONS:
        return (2, 0, len(path.parts), relative.lower())
    return (3, 0, len(path.parts), relative.lower())


def _is_candidate(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    # Do not follow repository symlinks, which could point outside the clone.
    if path.is_symlink():
        return False
    if any(part.lower() in IGNORED_DIRS for part in relative.parts[:-1]):
        return False
    lower_name = path.name.lower()
    if lower_name in LOCK_FILES or any(part in lower_name for part in GENERATED_PARTS):
        return False
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False
    try:
        return path.stat().st_size <= MAX_FILE_CHARS * 4
    except OSError:
        return False


def _read_text(path: Path) -> str | None:
    """Read likely text files as UTF-8; reject binary or mostly undecodable data."""
    try:
        raw = path.read_bytes()
        if b"\x00" in raw:
            return None
        text = raw.decode("utf-8", errors="replace")
        if text and text.count("\ufffd") / len(text) > 0.01:
            return None
        return text
    except OSError:
        return None


def _language(path: Path) -> str:
    return {
        ".py": "python", ".js": "javascript", ".jsx": "jsx", ".ts": "typescript",
        ".tsx": "tsx", ".java": "java", ".cpp": "cpp", ".h": "c",
        ".hpp": "cpp", ".cs": "csharp", ".go": "go", ".rs": "rust",
        ".php": "php", ".rb": "ruby", ".swift": "swift", ".kt": "kotlin",
        ".html": "html", ".css": "css", ".scss": "scss", ".sql": "sql",
        ".sh": "bash", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
        ".toml": "toml", ".md": "markdown", ".c": "c",
    }.get(path.suffix.lower(), "text")


def _build_context(root: Path, max_chars: int) -> tuple[list[str], str]:
    candidates = sorted(
        (path for path in root.rglob("*") if path.is_file() and _is_candidate(path, root)),
        key=lambda path: _rank_file(path, root),
    )
    chosen: list[str] = []
    sections: list[str] = []
    remaining = max_chars
    for path in candidates:
        text = _read_text(path)
        if text is None or not text.strip():
            continue
        relative = path.relative_to(root).as_posix()
        header = f"FILE: {relative}\n```{_language(path)}\n"
        footer = "\n```\n\n"
        available = remaining - len(header) - len(footer)
        if available <= 0:
            break
        body = text[: min(available, MAX_FILE_CHARS)]
        if len(body) < len(text) and len(body) >= 80:
            body += "\n[File content truncated]"
        section = header + body + footer
        if len(section) > remaining:
            break
        sections.append(section)
        chosen.append(relative)
        remaining -= len(section)
    return chosen, "".join(sections)


def analyze_repository(repo_url: str, max_context_chars: int = 60_000) -> RepositoryContext:
    """Clone shallowly, select readable files, and always remove the temporary clone."""
    if not validate_github_url(repo_url):
        raise ValueError("Please provide a valid public GitHub repository URL.")
    parsed = urlparse(repo_url.strip())
    repository = parsed.path.strip("/").split("/")[-1].removesuffix(".git")
    clone_url = repo_url.strip().removesuffix("/")
    if not clone_url.endswith(".git"):
        clone_url += ".git"
    try:
        with tempfile.TemporaryDirectory(prefix="github-code-explainer-") as temp_dir:
            clone_options = {
                "depth": 1,
                "no_checkout": False,
                "env": {
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_CONFIG_COUNT": "2",
                    "GIT_CONFIG_KEY_0": "http.lowSpeedLimit",
                    "GIT_CONFIG_VALUE_0": "1000",
                    "GIT_CONFIG_KEY_1": "http.lowSpeedTime",
                    "GIT_CONFIG_VALUE_1": "60",
                },
            }
            # GitPython's kill_after_timeout is supported on Render/Linux, but
            # explicitly unsupported by its Windows subprocess implementation.
            if os.name != "nt":
                clone_options["kill_after_timeout"] = 120
            Repo.clone_from(clone_url, temp_dir, **clone_options)
            files, context = _build_context(Path(temp_dir), max(1, max_context_chars))
            return RepositoryContext(repository, files, context)
    except GitCommandError as exc:
        raise RuntimeError(
            "Unable to clone the repository. Check the URL and confirm it is public."
        ) from exc
