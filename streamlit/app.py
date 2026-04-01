"""
streamlit/app.py
Main entry point for Living API Docs Streamlit app.
Initialises DB, starts background poller, renders sidebar navigation.
"""

import sys
import os

# Add project root to path so all modules resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from storage.db import init_db
from poller.poller import start_poller

# ── Page config (must be first Streamlit call) ──
st.set_page_config(
    page_title="Living API Docs",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Global CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --primary: #00d4aa;
        --primary-dark: #00a885;
        --bg-dark: #0d1117;
        --bg-card: #161b22;
        --bg-card2: #1c2128;
        --border: #30363d;
        --text: #e6edf3;
        --text-muted: #8b949e;
        --accent-blue: #58a6ff;
        --accent-orange: #f78166;
        --accent-yellow: #e3b341;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: var(--bg-dark);
        color: var(--text);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: var(--bg-card) !important;
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] * {
        color: var(--text) !important;
    }

    /* Main content padding */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    /* Cards */
    .api-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s;
    }

    .api-card:hover {
        border-color: var(--primary);
    }

    /* Method badges */
    .badge-get    { background: #1a7f37; color: #fff; padding: 2px 10px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 600; }
    .badge-post   { background: #9a6700; color: #fff; padding: 2px 10px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 600; }
    .badge-put    { background: #0969da; color: #fff; padding: 2px 10px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 600; }
    .badge-patch  { background: #6e40c9; color: #fff; padding: 2px 10px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 600; }
    .badge-delete { background: #cf222e; color: #fff; padding: 2px 10px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 600; }

    /* Status badges */
    .status-pending  { color: var(--accent-yellow); font-weight: 600; }
    .status-approved { color: var(--primary); font-weight: 600; }
    .status-rejected { color: var(--accent-orange); font-weight: 600; }

    /* Buttons */
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.9rem;
        transition: all 0.15s;
    }

    /* Warning box */
    .warning-box {
        background: rgba(227, 179, 65, 0.1);
        border: 1px solid var(--accent-yellow);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.75rem 0;
        font-size: 0.88rem;
    }

    /* Route display */
    .route-text {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.95rem;
        color: var(--accent-blue);
    }

    /* Hero banner */
    .hero {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #1c2128 100%);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 2rem 2.5rem;
        margin-bottom: 2rem;
    }

    .hero h1 {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00d4aa, #58a6ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }

    .hero p {
        color: var(--text-muted);
        font-size: 1rem;
    }

    /* Divider */
    hr { border-color: var(--border) !important; }
</style>
""", unsafe_allow_html=True)


# ── One-time initialisation ──
@st.cache_resource
def initialise():
    """Run once: init DB and start background poller."""
    init_db()
    start_poller()
    return True


initialise()

# ── Auth gate — ensure user is logged in ──
from storage.db import ensure_users_table, get_user_by_token
ensure_users_table()

# Check token in URL params (coming from magic link)
params = st.query_params
url_token = params.get("token", None)
if url_token and not st.session_state.get("user_email"):
    user = get_user_by_token(url_token)
    if user:
        st.session_state["user_email"] = user["email"]
        st.session_state["user_token"] = url_token
        st.query_params.clear()

# If not logged in — show login prompt on home page
if not st.session_state.get("user_email"):
    st.markdown("""
    <div class="hero">
        <h1>Welcome to Living API Docs</h1>
        <p>Please sign in to start monitoring your APIs and generating documentation.</p>
    </div>
    """, unsafe_allow_html=True)
    st.info("👈 Go to **Sign In** in the sidebar to get started.")
    st.stop()


# ── Sidebar ──
with st.sidebar:
    st.markdown("""
    <div style="padding: 1rem 0 1.5rem; border-bottom: 1px solid #30363d; margin-bottom: 1.5rem;">
        <div style="font-size: 1.4rem; font-weight: 700; color: #00d4aa;">📄 Living API Docs</div>
        <div style="font-size: 0.78rem; color: #8b949e; margin-top: 0.25rem;">AI-powered documentation</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Navigation")
    st.page_link("app.py", label="🏠 Home", icon=None)
    st.page_link("pages/1_repo_scan.py", label="🔍 Repo Scanner")
    st.page_link("pages/2_review_draft.py", label="✏️ Review Drafts")
    st.page_link("pages/3_history.py", label="📚 Version History")

    st.markdown("---")

    # Monitored repos quick list
    from storage.db import get_all_repos
    repos = get_all_repos()
    if repos:
        st.markdown("### Monitored Repos")
        for r in repos[:5]:
            name = r["repo_url"].split("/")[-1].replace(".git", "")
            fw = r.get("framework") or "detecting..."
            st.markdown(f"**{name}** · `{fw}`")
    else:
        st.caption("No repos added yet. Go to Repo Scanner to add one.")

    st.markdown("---")
    st.caption("Living API Docs · Built with Groq + FAISS")


# ── Home Page ──
st.markdown("""
<div class="hero">
    <h1>Living API Docs</h1>
    <p>Event-driven, AI-augmented documentation that updates itself whenever your API changes.</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    repos = get_all_repos() if 'get_all_repos' in dir() else []
    from storage.db import get_all_repos
    repos = get_all_repos()
    st.metric("Repos Monitored", len(repos))

with col2:
    from storage.db import get_connection
    try:
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM drafts WHERE status='pending'").fetchone()[0]
        conn.close()
    except Exception:
        count = 0
    st.metric("Pending Reviews", count)

with col3:
    try:
        conn = get_connection()
        approved = conn.execute("SELECT COUNT(*) FROM version_history").fetchone()[0]
        conn.close()
    except Exception:
        approved = 0
    st.metric("Docs Published", approved)

st.markdown("---")

st.markdown("### How It Works")
col_a, col_b, col_c, col_d = st.columns(4)
with col_a:
    st.markdown("**1. 🔗 Add Repo**\nPaste your GitHub repo URL in the Repo Scanner page")
with col_b:
    st.markdown("**2. 🔍 Auto Detect**\nSystem detects framework & parses all API endpoints")
with col_c:
    st.markdown("**3. 🤖 AI Generate**\nLLM generates comprehensive docs with examples")
with col_d:
    st.markdown("**4. ✅ Review & Publish**\nReview drafts, approve, and publish to GitHub Pages")
