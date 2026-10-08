"""Streamlit user interface for the repository explainer."""

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="GitHub Repository Code Explainer", page_icon="📘")
st.title("GitHub Repository Code Explainer")
st.write(
    "Analyze a public GitHub repository with a local AI model and get a clear, "
    "beginner-friendly explanation. Repository files are read as text and never executed."
)

repo_url = st.text_input(
    "GitHub Repository URL", placeholder="https://github.com/username/repository"
)

if st.button("Explain Repository", type="primary"):
    if not repo_url.strip():
        st.error("Enter a public GitHub repository URL.")
    else:
        try:
            with st.spinner("Cloning and analyzing the repository with local Ollama…"):
                response = requests.post(
                    f"{API_URL}/explain", json={"repo_url": repo_url.strip()}, timeout=360
                )
            if not response.ok:
                try:
                    message = response.json().get("detail", response.text)
                except ValueError:
                    message = response.text
                st.error(str(message))
            else:
                result = response.json()
                st.subheader(f"Repository: {result['repository']}")
                files = result.get("files_analyzed", [])
                st.caption(f"{len(files)} relevant file(s) analyzed")
                with st.expander("Files analyzed", expanded=False):
                    for file_name in files:
                        st.code(file_name, language=None)
                st.subheader("Repository explanation")
                st.markdown(result["explanation"])
        except requests.RequestException as exc:
            st.error(f"Could not reach the FastAPI backend at {API_URL}: {exc}")
