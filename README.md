# GitHub Repository Code Explainer

Understand a public GitHub repository with a beginner-friendly explanation of its structure, technologies, important files, and application flow. The project supports a local Ollama setup and an online Groq setup. Repository files are cloned temporarily and read as text; repository code is never executed.

## Architecture

```text
GitHub URL → GitPython shallow clone → ranked text-file selection → bounded context
          → selected LLM provider → FastAPI response → Streamlit or static web frontend
```

The API entry point is `backend/main.py`. Repository filtering and extraction live in `backend/services/repository_processor.py`. Provider selection changes only the explanation step.

## Local version

The academic/demo setup uses Streamlit, FastAPI, GitPython, and Ollama with `rafw007/qwen35-codex-coder:9b`.

1. Install Python, Git, and Ollama.
2. Create a virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

3. Set `LLM_PROVIDER=ollama`, `OLLAMA_URL=http://localhost:11434`, and `OLLAMA_MODEL=rafw007/qwen35-codex-coder:9b` in the ignored local `.env`. Make sure the model is installed in Ollama.
4. In one terminal, run the API:

   ```text
   uvicorn backend.main:app --reload
   ```

5. In another terminal, run the Streamlit app:

   ```text
   streamlit run frontend/app.py
   ```

The local web frontend is also available using a static server: run `python -m http.server 3000 --directory frontend`, then open `http://localhost:3000`. Its API URL is configured in `frontend/config.js`.

## Online version

The online setup uses the static HTML/CSS/JavaScript frontend, FastAPI on Render, GitPython, and Groq API. The browser communicates only with FastAPI. The Groq key is read by the backend from `GROQ_API_KEY`; it must be configured as a private Render environment variable. Ollama is not contacted when `LLM_PROVIDER=groq`.

The Groq model defaults to `openai/gpt-oss-20b` and can be changed with `GROQ_MODEL`. Groq's current [model deprecation notice](https://console.groq.com/docs/deprecations) lists this model as shut down for standard free and developer accounts from August 16, 2026; check availability for your account and set `GROQ_MODEL` to an available replacement if needed. Local development settings are loaded from `.env`. The checked-in `.env.example` intentionally contains only an empty `GROQ_API_KEY=` line; keep all actual keys in `.env`, which is ignored by Git.

### Run the online backend locally

Install the project requirements, put the key into your local ignored `.env`, and set:

```text
LLM_PROVIDER=groq
GROQ_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=<your key in the local .env only>
MAX_CONTEXT_CHARS=60000
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8501
```

Start the API with `uvicorn backend.main:app --reload`. Serve the static frontend with `python -m http.server 3000 --directory frontend`. `frontend/config.js` defaults to the local API at `http://localhost:8000`.

### Deploy to Render

1. Push the project to a GitHub repository. Confirm `.env` is ignored and contains no committed key.
2. Create or use a Groq API key. Do not paste it into source files, the frontend, or this README.
3. In Render, create a Blueprint from the repository using `render.yaml`, or create the services manually.
4. For the backend Web Service, use build command `pip install -r requirements.txt` and start command `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
5. Set backend environment variables in Render:

   - `LLM_PROVIDER=groq`
   - `GROQ_MODEL=openai/gpt-oss-20b`
   - `GROQ_API_KEY` set privately in the Render dashboard
   - `MAX_CONTEXT_CHARS=60000`
   - `ALLOWED_ORIGINS=https://<your-static-site>.onrender.com`

6. Deploy the backend and check its `/health` and `/docs` URLs.
7. Deploy a Render Static Site with publish directory `frontend` (already described in `render.yaml`).
8. Set `frontend/config.js` `API_BASE_URL` to the deployed backend URL, commit and redeploy the static site.
9. Set backend `ALLOWED_ORIGINS` to the exact static-site origin, without a trailing slash, and redeploy the backend if needed.
10. Submit a small public GitHub repository URL in the website and check the generated report.

Render filesystems are ephemeral. Each clone is created in a unique temporary directory and removed after analysis, including when an error occurs. `/health` does not contact GitHub or either LLM provider. API documentation remains at `/docs` and `/openapi.json`.

## Frontend

The production frontend is plain HTML, CSS, and JavaScript in `frontend/index.html`, `frontend/style.css`, and `frontend/app.js`. It has responsive layouts, URL validation, loading and error states, a file list, and safe text-based Markdown rendering. `frontend/config.js` is the single place to set the backend URL; it contains no secrets.

## Security and limits

- Only HTTPS public GitHub repository URLs are accepted; arbitrary Git servers are rejected.
- The backend never imports or runs target repository code, installs its dependencies, or runs its scripts.
- `.git`, dependency, build, cache, editor, generated, binary, lock, and oversized files are excluded.
- Repository context is capped at 60,000 characters by default.
- Groq and Git operations have time limits, and API errors do not include credentials or SDK diagnostics.
- CORS is controlled by `ALLOWED_ORIGINS`; production should list only the deployed frontend origin.
- Large repositories may be truncated or omit files, so explanations describe only selected context.

## API

- `GET /` — API information
- `GET /health` — process health check
- `POST /explain` — analyze and explain a public GitHub repository

Example request body: `{"repo_url":"https://github.com/owner/repository"}`.

## Technologies

Python, FastAPI, Pydantic, Uvicorn, GitPython, Streamlit, Ollama, Groq Python SDK, python-dotenv, and plain HTML/CSS/JavaScript.
