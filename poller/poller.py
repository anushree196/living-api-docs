"""
poller/poller.py
Background daemon thread — polls all monitored repos for new commits.
When a change is detected, triggers the full pipeline:
  parse → embed → retrieve old doc → LLM generate → save draft
"""

import threading
import time
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))  # 30s default, 10s for demo

# Import pipeline modules
from storage import db
from parser.detect_framework import detect_framework, clone_or_pull_repo
from parser.fastapi_parser import parse_fastapi
from parser.flask_parser import parse_flask
from parser.django_parser import parse_django
from parser.express_parser import parse_express
from parser.springboot_parser import parse_springboot
from rag.embedder import embed_endpoint
from rag.vector_store import get_or_create_store, load_store
from rag.retriever import retrieve_old_doc
from llm.generator import generate_doc
from llm.consistency_checker import check_consistency


# Global state — tracks which repos are being monitored
_monitored_repos = set()
_lock = threading.Lock()
_poller_thread = None
_running = False


def get_github_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def parse_repo_url(repo_url: str):
    """
    Extract owner and repo name from a GitHub URL.
    Supports: https://github.com/owner/repo and https://github.com/owner/repo.git
    """
    repo_url = repo_url.rstrip("/").replace(".git", "")
    parts = repo_url.split("github.com/")
    if len(parts) < 2:
        return None, None
    path_parts = parts[1].split("/")
    if len(path_parts) < 2:
        return None, None
    return path_parts[0], path_parts[1]


def get_latest_commit_sha(owner: str, repo: str) -> str:
    """Fetch the latest commit SHA from the default branch via GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    try:
        response = requests.get(url, headers=get_github_headers(), timeout=10)
        if response.status_code == 200:
            commits = response.json()
            if commits:
                return commits[0]["sha"]
    except Exception as e:
        print(f"[Poller] Error fetching commits for {owner}/{repo}: {e}")
    return None


def get_changed_files(owner: str, repo: str, base_sha: str, head_sha: str) -> list:
    """Get list of files changed between two commits."""
    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}"
    try:
        response = requests.get(url, headers=get_github_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [f["filename"] for f in data.get("files", [])]
    except Exception as e:
        print(f"[Poller] Error fetching changed files: {e}")
    return []


def is_api_related_file(filename: str, framework: str) -> bool:
    """Check if a changed file is likely to contain API endpoint definitions."""
    filename_lower = filename.lower()

    # Always skip test files, migrations, static assets
    skip_patterns = ["test_", "_test.", "migration", ".css", ".html",
                     ".md", ".txt", ".json", ".yml", ".yaml", "static/"]
    for pattern in skip_patterns:
        if pattern in filename_lower:
            return False

    # Framework-specific API file patterns
    if framework == "fastapi":
        return any(k in filename_lower for k in ["router", "route", "main", "api", "endpoint"])
    elif framework == "flask":
        return filename.endswith(".py") and any(k in filename_lower for k in ["route", "view", "api", "app"])
    elif framework == "django":
        return filename.endswith(".py") and any(k in filename_lower for k in ["view", "url", "api"])
    elif framework == "express":
        return filename.endswith(".js") and any(k in filename_lower for k in ["route", "router", "api", "app", "index"])
    elif framework == "springboot":
        return filename.endswith(".java") and any(k in filename_lower for k in ["controller", "resource", "api"])

    # Generic fallback
    return filename.endswith((".py", ".js", ".java"))


def run_pipeline_for_repo(repo_url: str):
    """
    Full pipeline for a repo when changes are detected:
    1. Clone/pull latest code
    2. Detect framework
    3. Parse endpoints
    4. For each endpoint → retrieve old doc via RAG → generate new doc via LLM
    5. Run consistency check
    6. Save draft to DB
    """
    print(f"[Poller] Running pipeline for: {repo_url}")

    # Step 1 — Clone or pull latest
    local_path = clone_or_pull_repo(repo_url)
    if not local_path:
        print(f"[Poller] Failed to clone/pull {repo_url}")
        return

    # Step 2 — Detect framework
    framework = detect_framework(local_path)
    if not framework:
        print(f"[Poller] Could not detect framework for {repo_url}")
        return

    db.update_repo_framework(repo_url, framework)
    print(f"[Poller] Detected framework: {framework}")

    # Step 3 — Parse endpoints
    parsers = {
        "fastapi": parse_fastapi,
        "flask": parse_flask,
        "django": parse_django,
        "express": parse_express,
        "springboot": parse_springboot,
    }

    parser_fn = parsers.get(framework)
    if not parser_fn:
        print(f"[Poller] No parser for framework: {framework}")
        return

    endpoints = parser_fn(local_path)
    print(f"[Poller] Found {len(endpoints)} endpoints")

    if not endpoints:
        return

    # Load FAISS store for this repo (creates fresh one if first run)
    store = get_or_create_store(repo_url)

    # Step 4 — For each endpoint: RAG → LLM → save draft
    for ep in endpoints:
        method = ep.get("method", "GET")
        route = ep.get("route", "/")
        params = ep.get("params", [])
        return_type = ep.get("return_type", "")
        auth_required = ep.get("auth_required", False)
        raw_code = ep.get("raw_code", "")

        # Save/update endpoint in DB
        db.upsert_endpoint(
            repo_url, method, route, params,
            return_type, auth_required, raw_code
        )

        # Skip if pending draft already exists for this endpoint
        if db.has_pending_draft(repo_url, method, route):
            print(f"[Poller] Skipping {method} {route} — pending draft already exists")
            continue

        # Retrieve old doc from FAISS (None if first time)
        old_doc = retrieve_old_doc(store, method, route) if store else None

        # Generate new doc via LLM
        generated_doc = generate_doc(
            method=method,
            route=route,
            params=params,
            return_type=return_type,
            auth_required=auth_required,
            raw_code=raw_code,
            old_doc=old_doc,
            framework=framework
        )

        if not generated_doc:
            print(f"[Poller] LLM generation failed for {method} {route}")
            continue

        # Run consistency check
        warnings = check_consistency(generated_doc, raw_code)

        # Save draft to DB
        db.save_draft(repo_url, method, route, generated_doc, warnings)
        print(f"[Poller] Draft saved for {method} {route}")

        # Embed and add to FAISS store for future retrievals
        embed_endpoint(store, method, route, generated_doc, repo_url)

    print(f"[Poller] Pipeline complete for {repo_url}")


def _poll_loop():
    """Main polling loop — runs in daemon thread."""
    global _running
    print(f"[Poller] Daemon thread started. Interval: {POLL_INTERVAL}s")

    while _running:
        repos = db.get_all_repos()

        for repo in repos:
            repo_url = repo["repo_url"]
            last_sha = repo.get("last_commit_sha")

            owner, repo_name = parse_repo_url(repo_url)
            if not owner or not repo_name:
                continue

            latest_sha = get_latest_commit_sha(owner, repo_name)
            if not latest_sha:
                continue

            # First time — no previous SHA → run pipeline to generate initial docs
            if not last_sha:
                print(f"[Poller] First scan for {repo_url}")
                db.update_repo_commit(repo_url, latest_sha)
                run_pipeline_for_repo(repo_url)

            # Change detected
            elif latest_sha != last_sha:
                print(f"[Poller] Change detected in {repo_url}")
                changed_files = get_changed_files(owner, repo_name, last_sha, latest_sha)
                framework = repo.get("framework", "")

                api_changed = any(
                    is_api_related_file(f, framework) for f in changed_files
                )

                if api_changed:
                    print(f"[Poller] API-related files changed: {changed_files}")
                    db.update_repo_commit(repo_url, latest_sha)
                    run_pipeline_for_repo(repo_url)
                else:
                    print(f"[Poller] No API-related changes in {repo_url}, skipping.")
                    db.update_repo_commit(repo_url, latest_sha)
            else:
                print(f"[Poller] No changes in {repo_url}")

        time.sleep(POLL_INTERVAL)

    print("[Poller] Daemon thread stopped.")


def start_poller():
    """Start the background polling daemon thread. Safe to call multiple times."""
    global _poller_thread, _running

    if _poller_thread and _poller_thread.is_alive():
        print("[Poller] Already running.")
        return

    _running = True
    _poller_thread = threading.Thread(target=_poll_loop, daemon=True)
    _poller_thread.start()
    print("[Poller] Started.")


def stop_poller():
    """Gracefully stop the polling thread."""
    global _running
    _running = False
    print("[Poller] Stop signal sent.")


def trigger_manual_scan(repo_url: str):
    """
    Manually trigger a pipeline run for a specific repo.
    Used when user clicks 'Scan Now' in Streamlit UI.
    """
    thread = threading.Thread(
        target=run_pipeline_for_repo,
        args=(repo_url,),
        daemon=True
    )
    thread.start()
    print(f"[Poller] Manual scan triggered for {repo_url}")


# ─────────────────────────────────────────────
# EMAIL NOTIFICATION HOOK
# ─────────────────────────────────────────────

def notify_user_of_updates(repo_url: str, updated_endpoints: list):
    """
    Send email notification to repo owner when docs are updated.
    Called after pipeline completes with new drafts.
    """
    try:
        repo = db.get_repo(repo_url)
        if not repo or not repo.get("user_email"):
            return

        user_email = repo["user_email"]
        user = db.get_user_by_email(user_email)
        if not user:
            return

        from publisher.email_notifier import send_docs_updated_notification
        send_docs_updated_notification(
            to_email=user_email,
            repo_url=repo_url,
            updated_endpoints=updated_endpoints,
            token=user["token"]
        )
    except Exception as e:
        print(f"[Poller] Email notification failed: {e}")
