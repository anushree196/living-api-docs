"""
publisher/github_pages.py
Pushes generated documentation to the gh-pages branch of the target repo.
This makes docs live at: https://username.github.io/repo-name
Requires a GitHub Personal Access Token with repo write permissions.
"""

import os
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def _get_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }


def _parse_repo_url(repo_url: str):
    repo_url = repo_url.rstrip("/").replace(".git", "")
    parts = repo_url.split("github.com/")
    if len(parts) < 2:
        return None, None
    path_parts = parts[1].split("/")
    if len(path_parts) < 2:
        return None, None
    return path_parts[0], path_parts[1]


def _ensure_gh_pages_branch(owner: str, repo: str) -> bool:
    """
    Ensure gh-pages branch exists.
    Creates it from main/master if it doesn't exist.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/branches/gh-pages"
    response = requests.get(url, headers=_get_headers())

    if response.status_code == 200:
        return True  # Branch already exists

    # Get default branch SHA to create gh-pages from
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_response = requests.get(repo_url, headers=_get_headers())
    if repo_response.status_code != 200:
        print(f"[GHPages] Could not fetch repo info: {repo_response.text}")
        return False

    default_branch = repo_response.json().get("default_branch", "main")

    # Get SHA of default branch
    branch_url = f"https://api.github.com/repos/{owner}/{repo}/branches/{default_branch}"
    branch_response = requests.get(branch_url, headers=_get_headers())
    if branch_response.status_code != 200:
        print(f"[GHPages] Could not fetch {default_branch} branch: {branch_response.text}")
        return False

    sha = branch_response.json()["commit"]["sha"]

    # Create gh-pages branch
    create_url = f"https://api.github.com/repos/{owner}/{repo}/git/refs"
    create_response = requests.post(create_url, headers=_get_headers(), json={
        "ref": "refs/heads/gh-pages",
        "sha": sha
    })

    if create_response.status_code in (200, 201):
        print(f"[GHPages] Created gh-pages branch from {default_branch}")
        return True
    else:
        print(f"[GHPages] Failed to create gh-pages branch: {create_response.text}")
        return False


def _get_file_sha(owner: str, repo: str, filepath: str) -> str:
    """Get SHA of an existing file in gh-pages (needed for updates)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filepath}"
    params = {"ref": "gh-pages"}
    response = requests.get(url, headers=_get_headers(), params=params)
    if response.status_code == 200:
        return response.json().get("sha")
    return None


def _push_file(owner: str, repo: str, filepath: str, content: str, commit_message: str) -> bool:
    """Create or update a file in the gh-pages branch."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filepath}"

    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    existing_sha = _get_file_sha(owner, repo, filepath)

    payload = {
        "message": commit_message,
        "content": encoded_content,
        "branch": "gh-pages"
    }
    if existing_sha:
        payload["sha"] = existing_sha

    response = requests.put(url, headers=_get_headers(), json=payload)

    if response.status_code in (200, 201):
        return True
    else:
        print(f"[GHPages] Failed to push {filepath}: {response.text}")
        return False


def _markdown_to_html(markdown_content: str, repo_name: str) -> str:
    """
    Convert markdown to a simple styled HTML page for GitHub Pages.
    Uses a clean, readable documentation style.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{repo_name} API Documentation</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.7;
            color: #24292e;
            background: #f6f8fa;
        }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 2rem; }}
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 3rem 2rem;
            margin-bottom: 2rem;
            border-radius: 8px;
        }}
        .header h1 {{ font-size: 2rem; font-weight: 700; }}
        .header p {{ opacity: 0.8; margin-top: 0.5rem; }}
        .badge {{
            display: inline-block;
            background: #00d4aa;
            color: #1a1a2e;
            padding: 0.2rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            margin-top: 1rem;
        }}
        .content {{
            background: white;
            border-radius: 8px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        pre {{
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
            margin: 1rem 0;
            font-size: 0.9rem;
        }}
        code {{
            background: #f0f0f0;
            padding: 0.2rem 0.4rem;
            border-radius: 3px;
            font-size: 0.9rem;
        }}
        pre code {{ background: none; padding: 0; }}
        h1, h2, h3 {{
            margin: 1.5rem 0 0.75rem;
            color: #1a1a2e;
        }}
        h1 {{ font-size: 1.8rem; border-bottom: 2px solid #00d4aa; padding-bottom: 0.5rem; }}
        h2 {{ font-size: 1.4rem; border-bottom: 1px solid #eee; padding-bottom: 0.3rem; }}
        h3 {{ font-size: 1.1rem; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.9rem;
        }}
        th {{
            background: #f6f8fa;
            border: 1px solid #ddd;
            padding: 0.6rem 1rem;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            border: 1px solid #ddd;
            padding: 0.6rem 1rem;
        }}
        tr:hover {{ background: #f9f9f9; }}
        p {{ margin: 0.75rem 0; }}
        ul, ol {{ margin: 0.75rem 0 0.75rem 2rem; }}
        hr {{ border: none; border-top: 1px solid #eee; margin: 2rem 0; }}
        .footer {{
            text-align: center;
            color: #666;
            font-size: 0.85rem;
            margin-top: 2rem;
            padding: 1rem;
        }}
    </style>
    <!-- Markdown to HTML via marked.js -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 {repo_name}</h1>
            <p>API Documentation</p>
            <span class="badge">Auto-Generated</span>
        </div>
        <div class="content" id="content"></div>
        <div class="footer">
            Generated by <strong>Living API Docs</strong> · {datetime.now().strftime('%Y-%m-%d')}
        </div>
    </div>
    <script>
        const markdown = {repr(markdown_content)};
        document.getElementById('content').innerHTML = marked.parse(markdown);
    </script>
</body>
</html>"""




def _enable_github_pages(owner: str, repo: str) -> bool:
    """Enable GitHub Pages from gh-pages branch via API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pages"
    
    # Check if already enabled
    check = requests.get(url, headers=_get_headers())
    if check.status_code == 200:
        print(f"[GHPages] Pages already enabled for {owner}/{repo}")
        return True
    
    # Enable it
    response = requests.post(url, headers=_get_headers(), json={
        "source": {"branch": "gh-pages", "path": "/"}
    })
    if response.status_code in (200, 201):
        print(f"[GHPages] GitHub Pages enabled for {owner}/{repo}")
        return True
    else:
        print(f"[GHPages] Could not auto-enable Pages: {response.status_code} {response.text[:100]}")
        print(f"[GHPages] Please enable manually: github.com/{owner}/{repo}/settings/pages")
        return True  # Return True anyway — files are pushed, just needs manual enable

def publish_to_github_pages(repo_url: str, markdown_path: str) -> str:
    """
    Push documentation to gh-pages branch of the repo.

    Args:
        repo_url: GitHub repo URL
        markdown_path: Local path to the generated markdown file

    Returns:
        Published GitHub Pages URL, or None on failure.
    """
    if not GITHUB_TOKEN:
        print("[GHPages] No GitHub token found. Cannot publish.")
        return None

    owner, repo_name = _parse_repo_url(repo_url)
    if not owner or not repo_name:
        print(f"[GHPages] Invalid repo URL: {repo_url}")
        return None

    # Read markdown content
    try:
        with open(markdown_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
    except Exception as e:
        print(f"[GHPages] Could not read markdown file: {e}")
        return None

    # Ensure gh-pages branch exists
    if not _ensure_gh_pages_branch(owner, repo_name):
        return None

    # Enable GitHub Pages on this repo
    _enable_github_pages(owner, repo_name)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    # Push HTML version (main docs page)
    html_content = _markdown_to_html(markdown_content, repo_name)
    html_success = _push_file(
        owner, repo_name, "index.html", html_content,
        f"docs: auto-update API documentation [{timestamp}]"
    )

    # Push raw markdown as well
    md_success = _push_file(
        owner, repo_name, "API_DOCS.md", markdown_content,
        f"docs: update API_DOCS.md [{timestamp}]"
    )

    if html_success:
        pages_url = f"https://{owner}.github.io/{repo_name}"
        print(f"[GHPages] Files pushed. Pages URL: {pages_url}")
        print(f"[GHPages] If 404: go to github.com/{owner}/{repo_name}/settings/pages and set branch to gh-pages")
        return pages_url
    else:
        print("[GHPages] Failed to publish HTML.")
        return None