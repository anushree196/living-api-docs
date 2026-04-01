"""
publisher/email_notifier.py
SendGrid email notifications for Living API Docs.
Sends magic login links + doc update alerts to users.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@livingapidocs.com")
APP_URL = os.getenv("APP_URL", "http://localhost:8501")
SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via SendGrid API."""
    if not SENDGRID_API_KEY:
        print(f"[Email] No SendGrid key — skipping email to {to_email}")
        return False

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": FROM_EMAIL, "name": "Living API Docs"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}]
    }

    try:
        response = requests.post(
            SENDGRID_URL,
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=15
        )
        if response.status_code in (200, 202):
            print(f"[Email] Sent to {to_email}: {subject}")
            return True
        else:
            print(f"[Email] Failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"[Email] Error: {e}")
        return False


def send_magic_link(to_email: str, token: str) -> bool:
    """Send magic login link — no password needed."""
    login_url = f"{APP_URL}/?token={token}"

    html = f"""
    <div style="font-family:sans-serif;max-width:500px;margin:0 auto;padding:2rem;">
        <div style="background:linear-gradient(135deg,#0d1117,#161b22);
                    padding:2rem;border-radius:12px;text-align:center;margin-bottom:1.5rem;">
            <h1 style="color:#00d4aa;font-size:1.5rem;margin:0;">📄 Living API Docs</h1>
            <p style="color:#8b949e;margin-top:0.5rem;font-size:0.9rem;">
                AI-powered documentation that updates itself
            </p>
        </div>
        <p style="color:#24292e;font-size:1rem;">
            Click the button below to sign in. This link expires in 24 hours.
        </p>
        <div style="text-align:center;margin:2rem 0;">
            <a href="{login_url}"
               style="background:#00d4aa;color:#0d1117;padding:0.75rem 2rem;
                      border-radius:8px;text-decoration:none;font-weight:700;
                      font-size:1rem;display:inline-block;">
                🔐 Sign In to Living API Docs
            </a>
        </div>
        <p style="color:#8b949e;font-size:0.8rem;text-align:center;">
            If you didn't request this, ignore this email.
        </p>
    </div>
    """
    return _send(to_email, "🔐 Your Living API Docs Login Link", html)


def send_docs_updated_notification(to_email: str, repo_url: str,
                                    updated_endpoints: list, token: str) -> bool:
    """Send notification when API docs are auto-updated."""
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    review_url = f"{APP_URL}/?token={token}&page=review"

    endpoints_html = "".join([
        f'<li style="margin:0.3rem 0;font-family:monospace;color:#58a6ff;">'
        f'{ep.get("method","GET")} {ep.get("route","/")} </li>'
        for ep in updated_endpoints[:10]
    ])

    html = f"""
    <div style="font-family:sans-serif;max-width:500px;margin:0 auto;padding:2rem;">
        <div style="background:linear-gradient(135deg,#0d1117,#161b22);
                    padding:2rem;border-radius:12px;margin-bottom:1.5rem;">
            <h1 style="color:#00d4aa;font-size:1.5rem;margin:0;">📄 Living API Docs</h1>
            <p style="color:#8b949e;margin-top:0.5rem;font-size:0.9rem;">
                Your API changed — docs have been auto-updated!
            </p>
        </div>

        <div style="background:#f6f8fa;border-radius:8px;padding:1.25rem;margin-bottom:1.5rem;">
            <p style="margin:0;font-weight:600;color:#24292e;">
                📁 Repository: <code>{repo_name}</code>
            </p>
            <p style="margin:0.5rem 0 0;color:#57606a;font-size:0.9rem;">
                {len(updated_endpoints)} endpoint(s) updated:
            </p>
            <ul style="margin:0.5rem 0;padding-left:1.5rem;color:#24292e;">
                {endpoints_html}
            </ul>
        </div>

        <p style="color:#24292e;">
            New documentation drafts are ready for your review.
            Click below to review and approve:
        </p>

        <div style="text-align:center;margin:1.5rem 0;">
            <a href="{review_url}"
               style="background:#00d4aa;color:#0d1117;padding:0.75rem 2rem;
                      border-radius:8px;text-decoration:none;font-weight:700;
                      font-size:1rem;display:inline-block;">
                ✏️ Review Updated Docs
            </a>
        </div>

        <p style="color:#8b949e;font-size:0.8rem;text-align:center;">
            You're receiving this because you monitor <strong>{repo_name}</strong>
            on Living API Docs.
        </p>
    </div>
    """
    return _send(
        to_email,
        f"📄 [{repo_name}] API docs auto-updated — {len(updated_endpoints)} endpoint(s) changed",
        html
    )
