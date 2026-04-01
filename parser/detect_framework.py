"""
parser/detect_framework.py
Auto-detects the REST framework used in a GitHub repo.
Also handles cloning/pulling the repo to a local temp directory.
Supported: FastAPI, Flask, Django REST, Express.js, Spring Boot
"""

import os
import re
import subprocess
import shutil

# Where repos are cloned locally
CLONE_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cloned_repos")


def clone_or_pull_repo(repo_url: str) -> str:
    """
    Clone repo if not present, pull latest if already cloned.
    Returns local directory path, or None on failure.
    """
    os.makedirs(CLONE_BASE_DIR, exist_ok=True)

    # Derive a safe folder name from the URL
    safe_name = repo_url.rstrip("/").replace(".git", "").split("github.com/")[-1].replace("/", "_")
    local_path = os.path.join(CLONE_BASE_DIR, safe_name)

    try:
        if os.path.exists(local_path):
            # Pull latest changes
            result = subprocess.run(
                ["git", "-C", local_path, "pull"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                print(f"[Parser] Git pull failed: {result.stderr}")
                # If pull fails, delete and re-clone
                shutil.rmtree(local_path)
                _clone(repo_url, local_path)
        else:
            _clone(repo_url, local_path)

        return local_path

    except Exception as e:
        print(f"[Parser] clone_or_pull_repo error: {e}")
        return None


def _clone(repo_url: str, local_path: str):
    """Clone a repo to local_path."""
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, local_path],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git clone failed: {result.stderr}")
    print(f"[Parser] Cloned to {local_path}")


def _read_file_safe(path: str) -> str:
    """Read a file, return empty string on any error."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _find_files(local_path: str, extensions: list) -> list:
    """Recursively find all files with given extensions in local_path."""
    found = []
    for root, dirs, files in os.walk(local_path):
        # Skip hidden dirs, node_modules, venv, __pycache__
        dirs[:] = [d for d in dirs if not d.startswith(".")
                   and d not in ("node_modules", "venv", "env", "__pycache__",
                                 ".git", "migrations", "static", "tests")]
        for fname in files:
            if any(fname.endswith(ext) for ext in extensions):
                found.append(os.path.join(root, fname))
    return found


def detect_framework(local_path: str) -> str:
    """
    Detect the REST framework by inspecting project files.
    Returns one of: 'fastapi', 'flask', 'django', 'express', 'springboot', or None.
    Detection priority: most specific signals first.
    """

    # Check requirements.txt / setup.py for Python frameworks
    req_path = os.path.join(local_path, "requirements.txt")
    setup_path = os.path.join(local_path, "setup.py")
    req_content = _read_file_safe(req_path) + _read_file_safe(setup_path)

    if req_content:
        req_lower = req_content.lower()
        if "fastapi" in req_lower:
            return "fastapi"
        if "djangorestframework" in req_lower or "django-rest-framework" in req_lower:
            return "django"
        if "django" in req_lower:
            return "django"
        if "flask" in req_lower:
            return "flask"

    # Check package.json for Express
    pkg_path = os.path.join(local_path, "package.json")
    pkg_content = _read_file_safe(pkg_path)
    if pkg_content and "express" in pkg_content.lower():
        return "express"

    # Check pom.xml / build.gradle for Spring Boot
    pom_path = os.path.join(local_path, "pom.xml")
    gradle_path = os.path.join(local_path, "build.gradle")
    pom_content = _read_file_safe(pom_path) + _read_file_safe(gradle_path)
    if pom_content and "spring-boot" in pom_content.lower():
        return "springboot"

    # Fallback — scan Python files for import signatures
    py_files = _find_files(local_path, [".py"])
    for fpath in py_files[:20]:  # sample first 20 files
        content = _read_file_safe(fpath)
        if "from fastapi" in content or "import fastapi" in content.lower():
            return "fastapi"
        if "from flask" in content or "import flask" in content.lower():
            return "flask"
        if "from django" in content or "import django" in content.lower():
            return "django"

    # Fallback — scan JS files for Express
    js_files = _find_files(local_path, [".js"])
    for fpath in js_files[:10]:
        content = _read_file_safe(fpath)
        if "require('express')" in content or 'require("express")' in content:
            return "express"

    return None
