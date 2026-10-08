"""Streamlit interface for the GitHub Repository Code Explainer."""

import os
from urllib.parse import urlparse

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def resolve_backend_url(secrets=None, environ=None):
    """Resolve the API root from Streamlit Secrets or local environment."""
    secrets = secrets or {}
    environ = os.environ if environ is None else environ
    return str(
        secrets.get("backend_url")
        or secrets.get("BACKEND_URL")
        or environ.get("BACKEND_URL")
        or environ.get("backend_url")
        or "http://localhost:8000"
    ).strip().rstrip("/")


try:
    API_URL = resolve_backend_url(st.secrets)
except Exception:
    # Streamlit raises when no secrets file exists during local development.
    API_URL = resolve_backend_url()

st.set_page_config(page_title="GitHub Repository Code Explainer", page_icon="📘", layout="centered")
st.title("GitHub Repository Code Explainer")
st.markdown(
    """<style>
    .stApp { background: #0e1117; color: #f3f4f6; }
    [data-testid="stHeader"] { background: rgba(14,17,23,0); }
    .block-container { max-width: 900px; padding-top: 3rem; padding-bottom: 4rem; }
    h1 { font-size: clamp(2rem, 5vw, 3.1rem) !important; letter-spacing: -0.04em; }
    .hero-copy { color: #b9c0cc; font-size: 1.05rem; line-height: 1.65; }
    .safe-note { color: #99a3b3; font-size: .92rem; margin-top: -.25rem; }
    div[data-testid="stTextInput"] input { background: #242832; border: 1px solid #353b48; }
    div.stButton > button[kind="primary"] { background: #ef233c; border: 0; border-radius: 9px; }
    div.stButton > button[kind="primary"]:hover { background: #d91e35; border: 0; }
    .feature-row { display: flex; gap: 12px; margin: 1rem 0 1.6rem; flex-wrap: wrap; }
    .feature { border: 1px solid #303642; background: #171b23; color: #cbd2de; padding: 9px 13px; border-radius: 9px; font-size: .88rem; }
    [data-testid="stAlert"] { border-radius: 10px; }
    </style>
    <div class="hero-copy">Analyze a public GitHub repository and get a clear, beginner-friendly explanation of its structure and code.</div>
    <div class="safe-note">Repository files are read as text and never executed.</div>
    <div class="feature-row"><div class="feature">🔎 Relevant files only</div><div class="feature">🧠 AI powered analysis</div><div class="feature">🔒 Repository code is never run</div></div>""",
    unsafe_allow_html=True,
)

if "explain_result" not in st.session_state:
    st.session_state.explain_result = None

repo_url = st.text_input(
    "GitHub Repository URL", placeholder="https://github.com/username/repository"
)

if st.button("Explain Repository", type="primary", use_container_width=False):
    parsed = urlparse(repo_url.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or len(parsed.path.strip("/").split("/")) < 2:
        st.error("Enter a valid public GitHub URL, such as https://github.com/owner/repository.")
        st.session_state.explain_result = None
    else:
        try:
            with st.spinner("Cloning and analyzing repository files…"):
                response = requests.post(
                    f"{API_URL}/explain", json={"repo_url": repo_url.strip()}, timeout=360
                )
            if not response.ok:
                try:
                    detail = response.json().get("detail", "The analysis request failed.")
                except (ValueError, AttributeError):
                    detail = "The analysis request failed. Check the repository URL and try again."
                st.error(str(detail))
                st.session_state.explain_result = None
            else:
                st.session_state.explain_result = response.json()
        except requests.RequestException:
            st.error(
                f"Could not reach the analysis service at {API_URL}. Check that the Streamlit "
                "`backend_url` secret contains the deployed backend root URL and that its `/health` endpoint is available."
            )
            st.session_state.explain_result = None

result = st.session_state.explain_result
if result:
    st.divider()
    st.subheader(f"Repository: {result.get('repository', 'Analysis complete')}")
    files = result.get("files_analyzed", [])
    st.caption(f"{len(files)} relevant file(s) analyzed")
    with st.expander("Files analyzed", expanded=False):
        for file_name in files:
            st.code(file_name, language=None)
    st.subheader("Repository explanation")
    st.markdown(result.get("explanation", "No explanation was returned."))
