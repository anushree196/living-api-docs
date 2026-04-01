"""
streamlit/pages/3_history.py
Page 3 — Version History
Shows complete version history for all endpoints.
Allows side-by-side diff comparison between versions.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import difflib
from storage.db import get_all_repos, get_version_history, get_latest_published

st.set_page_config(page_title="Version History · Living API Docs", layout="wide")

st.markdown("# 📚 Version History")
st.markdown("Track every documentation update. Compare versions side by side.")
st.markdown("---")

# ── Repo selector ──
repos = get_all_repos()

if not repos:
    st.info("No repositories added yet. Go to Repo Scanner to add one.")
    st.stop()

repo_options = {r["repo_url"].split("/")[-1].replace(".git", ""): r["repo_url"] for r in repos}
selected_name = st.selectbox("Select Repository", list(repo_options.keys()))
selected_repo = repo_options[selected_name]

# ── Published URL ──
published = get_latest_published(selected_repo)
if published and published.get("published_url"):
    st.markdown(
        f"🌐 **Live Docs:** [{published['published_url']}]({published['published_url']})"
    )
    st.caption(f"Last published: {published.get('published_at', 'Unknown')}")

st.markdown("---")

# ── Full version history ──
all_history = get_version_history(selected_repo)

if not all_history:
    st.info("No version history yet. Approve some drafts on the Review page to start building history.")
    st.stop()

# Group by endpoint
from collections import defaultdict
grouped = defaultdict(list)
for record in all_history:
    key = f"{record['method']} {record['route']}"
    grouped[key].append(record)

st.markdown(f"**{len(grouped)} endpoints tracked · {len(all_history)} total versions**")
st.markdown("---")

# ── Endpoint selector for diff ──
st.markdown("### 🔍 Version Diff Viewer")
endpoint_keys = list(grouped.keys())
selected_endpoint = st.selectbox("Select Endpoint to Compare", endpoint_keys)

if selected_endpoint:
    versions = grouped[selected_endpoint]

    if len(versions) < 2:
        st.info("Only one version available for this endpoint. More versions appear as docs are updated over time.")
        st.markdown("#### Current Documentation")
        st.markdown(versions[0]["doc_content"])
    else:
        version_labels = [f"v{v['version_number']} — {v['approved_at'][:16]}" for v in versions]

        col1, col2 = st.columns(2)
        with col1:
            v1_label = st.selectbox("Version A", version_labels, index=len(version_labels) - 1, key="va")
        with col2:
            v2_label = st.selectbox("Version B", version_labels, index=0, key="vb")

        v1_idx = version_labels.index(v1_label)
        v2_idx = version_labels.index(v2_label)

        doc_a = versions[v1_idx]["doc_content"]
        doc_b = versions[v2_idx]["doc_content"]

        # Show diff
        diff = list(difflib.unified_diff(
            doc_a.splitlines(keepends=True),
            doc_b.splitlines(keepends=True),
            fromfile=v1_label,
            tofile=v2_label,
            lineterm=""
        ))

        if diff:
            diff_html_lines = []
            for line in diff:
                if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                    diff_html_lines.append(
                        f'<div style="color:#8b949e; font-family:monospace; font-size:0.82rem; padding:1px 6px;">'
                        f'{line}</div>'
                    )
                elif line.startswith("+"):
                    diff_html_lines.append(
                        f'<div style="background:rgba(26,127,55,0.2); color:#56d364; '
                        f'font-family:monospace; font-size:0.82rem; padding:1px 6px;">{line}</div>'
                    )
                elif line.startswith("-"):
                    diff_html_lines.append(
                        f'<div style="background:rgba(207,34,46,0.2); color:#ff7b72; '
                        f'font-family:monospace; font-size:0.82rem; padding:1px 6px;">{line}</div>'
                    )
                else:
                    diff_html_lines.append(
                        f'<div style="font-family:monospace; font-size:0.82rem; '
                        f'padding:1px 6px; color:#e6edf3;">{line}</div>'
                    )

            st.markdown("#### Changes")
            st.markdown(
                f'<div style="background:#0d1117; border:1px solid #30363d; border-radius:8px; '
                f'padding:1rem; max-height:500px; overflow-y:auto;">{"".join(diff_html_lines)}</div>',
                unsafe_allow_html=True
            )
        else:
            st.info("No differences between selected versions.")

        # Side by side view
        st.markdown("#### Side-by-Side View")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**{v1_label}**")
            with st.container():
                st.markdown(doc_a)
        with col_b:
            st.markdown(f"**{v2_label}**")
            with st.container():
                st.markdown(doc_b)

st.markdown("---")

# ── Full history table ──
st.markdown("### 📋 Complete History Log")

for endpoint_key, versions in grouped.items():
    method, route = endpoint_key.split(" ", 1)
    method_colors = {
        "GET": "#1a7f37", "POST": "#9a6700", "PUT": "#0969da",
        "PATCH": "#6e40c9", "DELETE": "#cf222e"
    }
    badge_color = method_colors.get(method, "#555")

    with st.expander(f"{method} {route} · {len(versions)} version(s)"):
        for v in versions:
            col1, col2, col3 = st.columns([1, 2, 3])
            with col1:
                st.markdown(
                    f'<span style="background:{badge_color}; color:#fff; '
                    f'padding:2px 8px; border-radius:4px; font-family:monospace; '
                    f'font-size:0.78rem;">v{v["version_number"]}</span>',
                    unsafe_allow_html=True
                )
            with col2:
                st.caption(v["approved_at"][:16])
            with col3:
                st.caption(v.get("change_summary") or "No summary")