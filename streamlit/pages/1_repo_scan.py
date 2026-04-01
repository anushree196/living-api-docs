"""
streamlit/pages/1_repo_scan.py
Page 1 — Repo Scanner
User pastes GitHub repo URL, system adds it to monitoring, triggers first scan.
Shows detected framework, endpoints found, and live polling status.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import time
from storage.db import add_repo, get_all_repos, get_repo, get_endpoints
from poller.poller import trigger_manual_scan, parse_repo_url, get_latest_commit_sha
from storage.db import init_db
init_db() # ← add this line
st.set_page_config(page_title="Repo Scanner · Living API Docs", layout="wide")

st.markdown("# 🔍 Repo Scanner")
st.markdown("Add a GitHub repository to start monitoring. The system will auto-detect the framework and generate documentation for all discovered API endpoints.")

st.markdown("---")

# ── Add New Repo ──
st.markdown("### Add Repository")

with st.form("add_repo_form"):
    repo_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/username/your-api-repo",
        help="Public or private repo. For private repos, ensure your GitHub token has access."
    )
    col1, col2 = st.columns([1, 4])
    with col1:
        submitted = st.form_submit_button("➕ Add & Scan", use_container_width=True, type="primary")

if submitted and repo_url:
    repo_url = repo_url.strip()

    # Validate it's a GitHub URL
    if "github.com" not in repo_url:
        st.error("Please enter a valid GitHub repository URL.")
    else:
        owner, repo_name = parse_repo_url(repo_url)

        if not owner or not repo_name:
            st.error("Could not parse repository URL. Format: https://github.com/owner/repo")
        else:
            # Check GitHub accessibility
            sha = get_latest_commit_sha(owner, repo_name)
            if not sha:
                st.error("Could not access this repository. Check the URL and ensure your GitHub token has access.")
            else:
                was_added = add_repo(repo_url)

                if was_added:
                    st.success(f"✅ **{repo_name}** added to monitoring!")
                    st.info("🔄 First scan triggered — this may take 1-2 minutes while the repo is cloned and endpoints are parsed.")
                    trigger_manual_scan(repo_url)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning(f"**{repo_name}** is already being monitored.")
                    if st.button("🔄 Trigger Manual Scan"):
                        trigger_manual_scan(repo_url)
                        st.success("Manual scan triggered!")

elif submitted and not repo_url:
    st.error("Please enter a repository URL.")

st.markdown("---")

# ── Monitored Repos ──
st.markdown("### Monitored Repositories")

repos = get_all_repos()

if not repos:
    st.info("No repositories added yet. Add one above to get started!")
else:
    for repo in repos:
        url = repo["repo_url"]
        name = url.split("/")[-1].replace(".git", "")
        framework = repo.get("framework") or "Detecting..."
        last_sha = repo.get("last_commit_sha", "")
        last_checked = repo.get("last_checked_at", "Never")

        # Get endpoint count
        endpoints = get_endpoints(url)
        ep_count = len(endpoints)

        with st.expander(f"📁 **{name}** · `{framework}` · {ep_count} endpoints", expanded=True):
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                st.markdown(f"🔗 [{url}]({url})")
                st.caption(f"Last checked: {last_checked}")
                if last_sha:
                    st.caption(f"Latest commit: `{last_sha[:8]}`")

            with col2:
                # Framework badge
                fw_colors = {
                    "fastapi": "🟢 FastAPI",
                    "flask": "🔵 Flask",
                    "django": "🟣 Django REST",
                    "express": "🟡 Express.js",
                    "springboot": "🔴 Spring Boot"
                }
                fw_display = fw_colors.get(framework, f"⚪ {framework}")
                st.markdown(f"**Framework:** {fw_display}")
                st.markdown(f"**Endpoints:** {ep_count} found")

            with col3:
                if st.button("🔄 Scan Now", key=f"scan_{url}"):
                    trigger_manual_scan(url)
                    st.success("Scan triggered!")

            # Show discovered endpoints
            if endpoints:
                st.markdown("**Discovered Endpoints:**")
                method_colors = {
                    "GET": "🟢", "POST": "🟡", "PUT": "🔵",
                    "PATCH": "🟣", "DELETE": "🔴"
                }
                for ep in endpoints:
                    icon = method_colors.get(ep["method"], "⚪")
                    auth_icon = "🔒" if ep.get("auth_required") else "🔓"
                    st.markdown(
                        f"{icon} `{ep['method']}` **{ep['route']}** {auth_icon} "
                        f"· `{ep.get('source_file', '')}`"
                    )
            else:
                st.caption("No endpoints discovered yet. Scan in progress...")

st.markdown("---")
st.caption("💡 The system polls for changes every 30 seconds. Trigger a manual scan anytime using the button above.")