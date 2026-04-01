"""
streamlit/pages/2_review_draft.py
Page 2 — Review & Approve Drafts
Shows AI-generated docs for each endpoint.
Dev can approve as-is, edit and approve, or reject.
Consistency warnings shown before approval.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
from storage.db import (
    get_all_repos, get_pending_drafts, get_all_drafts,
    approve_draft, reject_draft, save_version, get_endpoints
)
from llm.consistency_checker import verify_manual_edit, format_warnings_for_display
from publisher.markdown_exporter import export_markdown
from publisher.swagger_exporter import export_swagger
from publisher.github_pages import publish_to_github_pages

st.set_page_config(page_title="Review Drafts · Living API Docs", layout="wide")

st.markdown("# ✏️ Review Drafts")
st.markdown("Review AI-generated documentation. Approve as-is, edit before approving, or reject to regenerate.")
st.markdown("---")

# ── Repo selector ──
repos = get_all_repos()

if not repos:
    st.info("No repositories added yet. Go to **Repo Scanner** to add one.")
    st.stop()

repo_options = {r["repo_url"].split("/")[-1].replace(".git", ""): r["repo_url"] for r in repos}
selected_name = st.selectbox("Select Repository", list(repo_options.keys()))
selected_repo = repo_options[selected_name]

st.markdown("---")

# ── Filter tabs ──
tab1, tab2 = st.tabs(["⏳ Pending Review", "📋 All Drafts"])

def render_draft(draft: dict, repo_url: str, allow_actions: bool = True):
    """Render a single draft card with approve/edit/reject controls."""

    method = draft["method"]
    route = draft["route"]
    doc = draft["generated_doc"]
    warnings = draft.get("consistency_warnings", [])
    draft_id = draft["id"]
    status = draft["status"]

    method_colors = {
        "GET": "#1a7f37", "POST": "#9a6700", "PUT": "#0969da",
        "PATCH": "#6e40c9", "DELETE": "#cf222e"
    }
    badge_color = method_colors.get(method, "#555")

    st.markdown(f"""
    <div style="background:#161b22; border:1px solid #30363d; border-radius:10px;
                padding:1.25rem 1.5rem; margin-bottom:1rem;">
        <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.5rem;">
            <span style="background:{badge_color}; color:#fff; padding:2px 12px;
                         border-radius:4px; font-family:monospace; font-size:0.82rem;
                         font-weight:700;">{method}</span>
            <span style="font-family:monospace; font-size:1rem; color:#58a6ff;">{route}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Consistency warnings
    if warnings:
        st.markdown(f"""
        <div style="background:rgba(227,179,65,0.08); border:1px solid #e3b341;
                    border-radius:8px; padding:0.75rem 1rem; margin:0.5rem 0;">
            <strong style="color:#e3b341;">⚠️ Consistency Warnings</strong><br>
            {"<br>".join(f"• {w}" for w in warnings)}
            <br><em style="font-size:0.82rem; color:#8b949e;">
            These claims may not be supported by actual code. Verify before approving.</em>
        </div>
        """, unsafe_allow_html=True)

    # Preview / Edit toggle
    view_mode = st.radio(
        "View Mode",
        ["👁️ Preview", "✏️ Edit"],
        horizontal=True,
        key=f"view_mode_{draft_id}_{method}_{route}_{allow_actions}"
    )

    if view_mode == "👁️ Preview":
        st.markdown(doc)
        final_doc = doc

    else:  # Edit mode
        edited = st.text_area(
            "Edit Documentation",
            value=draft.get("edited_doc") or doc,
            height=500,
            key=f"edit_{draft_id}_{method}_{route}_{allow_actions}",
            help="Edit the AI-generated documentation. Only factual, code-supported claims will pass consistency check."
        )
        final_doc = edited

        # Re-run consistency check on edited content
        if edited != doc:
            # Get raw code for this endpoint
            endpoints = get_endpoints(repo_url)
            raw_code = next(
                (ep["raw_code"] for ep in endpoints
                 if ep["method"] == method and ep["route"] == route),
                ""
            )
            edit_warnings = verify_manual_edit(edited, raw_code or "")
            if edit_warnings:
                st.markdown(format_warnings_for_display(edit_warnings))
            else:
                st.success("✅ No consistency issues found in your edits.")

    # Action buttons
    if allow_actions and status == "pending":
        st.markdown("")
        col_approve, col_reject, col_spacer = st.columns([1, 1, 4])

        with col_approve:
            if st.button("✅ Approve", key=f"approve_{draft_id}_{method}_{route}_{allow_actions}", type="primary", use_container_width=True):
                approve_draft(draft_id, final_doc)
                # Save to version history
                save_version(
                    repo_url=repo_url,
                    method=method,
                    route=route,
                    doc_content=final_doc,
                    change_summary="Approved via review"
                )
                st.success(f"✅ **{method} {route}** approved and saved to version history!")
                st.rerun()

        with col_reject:
            if st.button("❌ Reject", key=f"reject_{draft_id}_{method}_{route}_{allow_actions}", use_container_width=True):
                reject_draft(draft_id)
                st.warning(f"Draft for **{method} {route}** rejected. Trigger a new scan to regenerate.")
                st.rerun()

    elif status == "approved":
        st.success("✅ Approved")
    elif status == "rejected":
        st.error("❌ Rejected")

    st.markdown("---")


# ── Tab 1: Pending ──
with tab1:
    pending = get_pending_drafts(selected_repo)

    if not pending:
        st.info("🎉 No pending drafts! All endpoints have been reviewed.")
        st.caption("Trigger a scan on the Repo Scanner page to generate new drafts when your API changes.")
    else:
        st.markdown(f"**{len(pending)} endpoint(s) awaiting review:**")
        for draft in pending:
            render_draft(draft, selected_repo, allow_actions=True)

# ── Tab 2: All Drafts ──
with tab2:
    all_drafts = get_all_drafts(selected_repo)

    if not all_drafts:
        st.info("No drafts yet for this repository.")
    else:
        # Filter controls
        filter_status = st.multiselect(
            "Filter by status",
            ["pending", "approved", "rejected"],
            default=["pending", "approved", "rejected"]
        )
        filtered = [d for d in all_drafts if d["status"] in filter_status]
        st.markdown(f"Showing **{len(filtered)}** drafts")
        for draft in filtered:
            render_draft(draft, selected_repo, allow_actions=(draft["status"] == "pending"))

st.markdown("---")

# ── Publish Section ──
st.markdown("### 🚀 Publish Documentation")
st.markdown("Export and publish all approved documentation for this repository.")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📄 Export Markdown", use_container_width=True):
        with st.spinner("Generating Markdown..."):
            md_path = export_markdown(selected_repo)
        if md_path:
            with open(md_path, "r") as f:
                content = f.read()
            st.download_button(
                "⬇️ Download Markdown",
                data=content,
                file_name=f"{selected_name}_api_docs.md",
                mime="text/markdown",
                use_container_width=True
            )
            st.success("Markdown generated!")
        else:
            st.error("No approved docs to export yet. Approve some drafts first.")

with col2:
    if st.button("📋 Export Swagger YAML", use_container_width=True):
        with st.spinner("Generating OpenAPI YAML..."):
            yaml_path = export_swagger(selected_repo)
        if yaml_path:
            with open(yaml_path, "r") as f:
                content = f.read()
            st.download_button(
                "⬇️ Download Swagger YAML",
                data=content,
                file_name=f"{selected_name}_swagger.yaml",
                mime="text/yaml",
                use_container_width=True
            )
            st.success("Swagger YAML generated!")
        else:
            st.error("No approved docs to export yet.")

with col3:
    if st.button("🌐 Publish to GitHub Pages", use_container_width=True):
        with st.spinner("Exporting and publishing..."):
            md_path = export_markdown(selected_repo)
            if md_path:
                pages_url = publish_to_github_pages(selected_repo, md_path)
                if pages_url:
                    st.success(f"🎉 Files pushed to gh-pages branch!")
                    st.markdown(f"**Live URL:** [{pages_url}]({pages_url})")
                    st.info(
                        "⏳ **If you see a 404:** GitHub Pages needs to be enabled manually once.\n\n"
                        f"Go to: `github.com/{selected_repo.split('github.com/')[-1]}/settings/pages` "
                        "→ Source → Deploy from branch → Select **gh-pages** → Save. "
                        "Takes 1-2 minutes to go live."
                    )
                else:
                    st.error("Publishing failed. Check your GitHub token has `repo` scope.")
            else:
                st.error("No approved docs to publish yet.")

st.caption("💡 GitHub Pages may take 1-2 minutes to go live after publishing.")