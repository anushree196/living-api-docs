"""
streamlit/pages/0_login.py
Email-based magic link authentication.
No passwords — user enters email, gets a login link, clicks it, done.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
from storage.db import create_or_get_user, get_user_by_token, ensure_users_table
from publisher.email_notifier import send_magic_link

st.set_page_config(page_title="Sign In · DocPulse ", layout="centered")

ensure_users_table()

# ── Check if token in URL params (magic link click) ──
params = st.query_params
token = params.get("token", None)

if token:
    user = get_user_by_token(token)
    if user:
        st.session_state["user_email"] = user["email"]
        st.session_state["user_token"] = token
        st.query_params.clear()
        st.switch_page("pages/1_repo_scan.py")
    else:
        st.error("Invalid or expired login link. Please request a new one.")

# ── Already logged in ──
if st.session_state.get("user_email"):
    st.success(f"✅ Signed in as **{st.session_state['user_email']}**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Go to Repo Scanner →", type="primary", use_container_width=True):
            st.switch_page("pages/1_repo_scan.py")
    with col2:
        if st.button("Sign Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    st.stop()

# ── Login Form ──
st.markdown("""
<div style="text-align:center; padding: 2rem 0 1rem;">
    <div style="font-size:3rem;">📄</div>
    <h1 style="font-size:2rem; font-weight:700; 
               background:linear-gradient(90deg,#00d4aa,#58a6ff);
               -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
        DocPulse - Living API Documentation System
    </h1>
    <p style="color:#8b949e; font-size:1rem;">
        AI-powered documentation that updates itself
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")
st.markdown("### Sign In")
st.markdown("Enter your email to receive a magic login link. No password needed.")

with st.form("login_form"):
    email = st.text_input(
        "Email Address",
        placeholder="you@example.com",
        help="We'll send documentation update alerts to this email"
    )
    submitted = st.form_submit_button("✉️ Send Magic Link", type="primary", use_container_width=True)

if submitted and email:
    if "@" not in email or "." not in email:
        st.error("Please enter a valid email address.")
    else:
        with st.spinner("Sending login link..."):
            user = create_or_get_user(email.strip().lower())
            if user:
                sent = send_magic_link(email, user["token"])
                if sent:
                    st.success(f"✅ Login link sent to **{email}**! Check your inbox.")
                    st.info("📧 Click the link in your email to sign in. "
                            "It will bring you straight back here.")
                else:
                    # SendGrid not configured — auto login for local dev
                    st.session_state["user_email"] = email.strip().lower()
                    st.session_state["user_token"] = user["token"]
                    st.success(f"✅ Signed in as **{email}** (local mode — no email sent)")
                    st.info("💡 Add SENDGRID_API_KEY to .env for real email magic links.")
                    st.switch_page("pages/1_repo_scan.py")
            else:
                st.error("Something went wrong. Please try again.")

elif submitted and not email:
    st.error("Please enter your email address.")

st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#8b949e; font-size:0.85rem;">
    <p>🔒 No password required · 📧 Email notifications when your API changes<br>
    📄 Export to Markdown, Swagger YAML, or GitHub Pages</p>
</div>
""", unsafe_allow_html=True)
