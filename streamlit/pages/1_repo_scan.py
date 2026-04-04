"""
streamlit/pages/1_repo_scan.py
Page 1 — Repo Scanner
User pastes GitHub repo URL, adds it to monitoring, triggers first scan.
Includes GitHub OAuth flow to auto-install webhooks on any repo.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import time
from storage.db import add_repo, get_all_repos, get_repo, get_endpoints
from poller.poller import trigger_manual_scan, parse_repo_url, get_latest_commit_sha

st.set_page_config(page_title="Repo Scanner · Living API Docs", layout="wide")

RAILWAY_URL = os.getenv("RAILWAY_WEBHOOK_URL", "")
USER_EMAIL  = st.session_state.get("user_email", "")

# ── Check for OAuth callback result ──
params = st.query_params
oauth_status = params.get("oauth", "")
oauth_repo   = params.get("repo", "")

if oauth_status == "webhook_installed":
    st.success(f"Webhook auto-installed on `{oauth_repo}`! Every push triggers automatic doc generation.")
    st.query_params.clear()
elif oauth_status == "authorized":
    st.info("GitHub authorized! Webhook will be installed when you add the repo below.")
    st.query_params.clear()

st.markdown("# Repo Scanner")
st.markdown("Add a GitHub repository to start monitoring.")
st.markdown("---")

with st.expander("How monitoring works — Polling vs Webhook", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Polling (always active)**\n- Checks GitHub every 30 seconds while app is open\n- No setup needed\n- Pauses when Streamlit sleeps")
    with col_b:
        st.markdown("**Webhook (recommended)**\n- Instant detection via Railway server\n- Works even when Streamlit is sleeping\n- Email notification with magic link\n- Requires one-click GitHub authorization")

st.markdown("---")
st.markdown("### Add Repository")

with st.form("add_repo_form"):
    repo_url = st.text_input("GitHub Repository URL", placeholder="https://github.com/username/your-api-repo")
    col1, col2 = st.columns([1, 4])
    with col1:
        submitted = st.form_submit_button("Add & Scan", use_container_width=True, type="primary")

if submitted and repo_url:
    repo_url = repo_url.strip()
    if "github.com" not in repo_url:
        st.error("Please enter a valid GitHub repository URL.")
    else:
        owner, repo_name = parse_repo_url(repo_url)
        if not owner or not repo_name:
            st.error("Could not parse URL. Format: https://github.com/owner/repo")
        else:
            sha = get_latest_commit_sha(owner, repo_name)
            if not sha:
                st.error("Could not access this repository. Check URL and GitHub token.")
            else:
                was_added = add_repo(repo_url)
                if was_added:
                    st.success(f"{repo_name} added to monitoring!")
                    st.info("First scan triggered — takes 1-2 minutes.")
                    trigger_manual_scan(repo_url)
                    if RAILWAY_URL and USER_EMAIL:
                        repo_full = f"{owner}/{repo_name}"
                        oauth_url = f"{RAILWAY_URL}/auth/start?email={USER_EMAIL}&repo={repo_full}"
                        st.markdown("---")
                        st.markdown("#### Enable Instant Webhook Notifications")
                        st.markdown("Connect GitHub to auto-install a webhook. You will get an email the moment your API changes — even when this app is sleeping.")
                        st.link_button("Connect GitHub & Enable Webhooks", url=oauth_url)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning(f"{repo_name} is already being monitored.")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("Trigger Manual Scan", use_container_width=True):
                            trigger_manual_scan(repo_url)
                            st.success("Scan triggered!")
                    with col_b:
                        if RAILWAY_URL and USER_EMAIL:
                            repo_full = f"{owner}/{repo_name}"
                            oauth_url = f"{RAILWAY_URL}/auth/start?email={USER_EMAIL}&repo={repo_full}"
                            st.link_button("Enable Webhook", url=oauth_url, use_container_width=True)

elif submitted and not repo_url:
    st.error("Please enter a repository URL.")

st.markdown("---")
st.markdown("### Monitored Repositories")

repos = get_all_repos()

if not repos:
    st.info("No repositories added yet. Add one above to get started!")
else:
    for repo in repos:
        url          = repo["repo_url"]
        name         = url.split("/")[-1].replace(".git", "")
        framework    = repo.get("framework") or "Detecting..."
        last_sha     = repo.get("last_commit_sha", "")
        last_checked = repo.get("last_checked_at", "Never")
        endpoints    = get_endpoints(url)
        ep_count     = len(endpoints)

        with st.expander(f"{name} · {framework} · {ep_count} endpoints", expanded=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"[{url}]({url})")
                st.caption(f"Last checked: {last_checked}")
                if last_sha:
                    st.caption(f"Latest commit: `{last_sha[:8]}`")
            with col2:
                fw_labels = {"fastapi":"FastAPI","flask":"Flask","django":"Django REST","express":"Express.js","springboot":"Spring Boot"}
                st.markdown(f"**Framework:** {fw_labels.get(framework, framework)}")
                st.markdown(f"**Endpoints:** {ep_count} found")
            with col3:
                if st.button("Scan Now", key=f"scan_{url}"):
                    trigger_manual_scan(url)
                    st.success("Scan triggered!")

            if RAILWAY_URL and USER_EMAIL:
                parts = url.split("github.com/")[-1].split("/")
                if len(parts) >= 2:
                    repo_full = f"{parts[0]}/{parts[1]}"
                    oauth_url = f"{RAILWAY_URL}/auth/start?email={USER_EMAIL}&repo={repo_full}"
                    st.link_button("Connect GitHub for Instant Webhooks", url=oauth_url)

            if endpoints:
                st.markdown("**Discovered Endpoints:**")
                method_icons = {"GET":"🟢","POST":"🟡","PUT":"🔵","PATCH":"🟣","DELETE":"🔴"}
                for ep in endpoints:
                    icon = method_icons.get(ep["method"], "⚪")
                    auth_icon = "🔒" if ep.get("auth_required") else "🔓"
                    st.markdown(f"{icon} `{ep['method']}` **{ep['route']}** {auth_icon} · `{ep.get('source_file', '')}`")
            else:
                st.caption("No endpoints discovered yet. Scan in progress...")

st.markdown("---")
st.caption("Polling checks every 30 seconds while app is open. Enable webhooks above for instant detection when sleeping.")
