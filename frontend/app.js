"use strict";

const apiBaseUrl = (window.APP_CONFIG?.API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const form = document.querySelector("#repo-form");
const input = document.querySelector("#repo-url");
const submitButton = document.querySelector("#submit-button");
const loadingState = document.querySelector("#loading-state");
const loadingMessage = document.querySelector("#loading-message");
const errorMessage = document.querySelector("#error-message");
const resultsSection = document.querySelector("#results");

function isGitHubRepositoryUrl(value) {
  try {
    const url = new URL(value);
    const pathParts = url.pathname.split("/").filter(Boolean);
    return url.protocol === "https:" && url.hostname === "github.com" && pathParts.length === 2;
  } catch {
    return false;
  }
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function addInlineText(parent, text) {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  for (const token of tokens) {
    if (token.startsWith("**") && token.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      parent.append(strong);
    } else if (token.startsWith("`") && token.endsWith("`")) {
      const code = document.createElement("code");
      code.textContent = token.slice(1, -1);
      parent.append(code);
    } else {
      parent.append(document.createTextNode(token));
    }
  }
}

function renderMarkdown(markdown, container) {
  container.replaceChildren();
  let activeList = null;
  let listType = "";
  for (const rawLine of markdown.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      activeList = null;
      listType = "";
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      activeList = null;
      const element = document.createElement(`h${Math.min(heading[1].length + 1, 4)}`);
      addInlineText(element, heading[2]);
      container.append(element);
      continue;
    }
    const unordered = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      const nextType = unordered ? "ul" : "ol";
      if (!activeList || nextType !== listType) {
        activeList = document.createElement(nextType);
        container.append(activeList);
        listType = nextType;
      }
      const item = document.createElement("li");
      addInlineText(item, (unordered || ordered)[1]);
      activeList.append(item);
      continue;
    }
    activeList = null;
    listType = "";
    const paragraph = document.createElement("p");
    addInlineText(paragraph, line.replace(/^>\s?/, ""));
    container.append(paragraph);
  }
}

function displayResult(result) {
  document.querySelector("#result-repository").textContent = result.repository;
  const files = Array.isArray(result.files_analyzed) ? result.files_analyzed : [];
  document.querySelector("#result-count").textContent = `${files.length} files analyzed`;
  document.querySelector("#files-total").textContent = String(files.length);
  const filesList = document.querySelector("#files-list");
  filesList.replaceChildren();
  for (const name of files) {
    const item = document.createElement("li");
    const icon = document.createElement("span");
    icon.className = "file-icon";
    icon.textContent = name.split(".").pop().slice(0, 3).toUpperCase();
    const label = document.createElement("span");
    label.textContent = name;
    item.append(icon, label);
    filesList.append(item);
  }
  renderMarkdown(result.explanation || "No explanation was returned.", document.querySelector("#explanation-content"));
  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.hidden = true;
  resultsSection.hidden = true;
  const repoUrl = input.value.trim();
  if (!isGitHubRepositoryUrl(repoUrl)) {
    showError("Please enter a valid public GitHub repository URL, such as https://github.com/owner/repository.");
    input.focus();
    return;
  }

  submitButton.disabled = true;
  loadingState.hidden = false;
  loadingMessage.textContent = "Cloning and selecting relevant files…";
  const messageTimer = window.setTimeout(() => {
    loadingMessage.textContent = "Generating the repository explanation…";
  }, 1800);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 300_000);
  try {
    const response = await fetch(`${apiBaseUrl}/explain`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl }),
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || "Unable to analyze this repository. Check that it is public and try again.");
    }
    displayResult(payload);
  } catch (error) {
    if (error.name === "AbortError") {
      showError("The analysis took too long. Please try again with a smaller repository.");
    } else if (error instanceof TypeError) {
      showError("Could not reach the analysis service. Please try again in a moment.");
    } else {
      showError(error.message || "Unable to analyze this repository. Please try again.");
    }
  } finally {
    window.clearTimeout(timeout);
    window.clearTimeout(messageTimer);
    loadingState.hidden = true;
    submitButton.disabled = false;
  }
});
