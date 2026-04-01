"""
parser/django_parser.py
Parses Django REST Framework ViewSets, APIViews, and url patterns.
"""

import os
import re
from parser.detect_framework import _find_files, _read_file_safe


def parse_django(local_path: str) -> list:
    endpoints = []
    py_files = _find_files(local_path, [".py"])

    for fpath in py_files:
        content = _read_file_safe(fpath)
        if not content:
            continue

        # urls.py files
        if "urls" in os.path.basename(fpath).lower() and "urlpatterns" in content:
            endpoints.extend(_extract_url_patterns(content, fpath))

        # views.py files with DRF ViewSets or APIViews
        if "views" in os.path.basename(fpath).lower() or "APIView" in content or "ViewSet" in content:
            endpoints.extend(_extract_drf_views(content, fpath))

    # Deduplicate by method+route
    seen = set()
    unique = []
    for ep in endpoints:
        key = (ep["method"], ep["route"])
        if key not in seen:
            seen.add(key)
            unique.append(ep)

    print(f"[Django Parser] Found {len(unique)} endpoints")
    return unique


def _extract_url_patterns(content: str, filepath: str) -> list:
    endpoints = []

    # Match: path("route/", view.as_view(), name="...") or path("route/", views.func)
    path_pattern = re.compile(r'path\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
    re_pattern = re.compile(r're_path\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)

    for pattern in [path_pattern, re_pattern]:
        for match in pattern.finditer(content):
            route = "/" + match.group(1).lstrip("/")
            # For URL patterns, we add GET and POST as defaults since Django
            # dispatches methods inside views — we'll refine in view parsing
            endpoints.append({
                "method": "GET",
                "route": route,
                "params": [],
                "return_type": "JSON",
                "auth_required": "IsAuthenticated" in content or "login_required" in content,
                "raw_code": match.group(0),
                "source_file": os.path.basename(filepath)
            })

    return endpoints


def _extract_drf_views(content: str, filepath: str) -> list:
    endpoints = []
    lines = content.split("\n")

    # Detect HTTP method handlers in APIView classes
    method_pattern = re.compile(r'def\s+(get|post|put|patch|delete)\s*\(self', re.IGNORECASE)

    current_class = None
    class_pattern = re.compile(r'^class\s+(\w+)\s*\(')

    for i, line in enumerate(lines):
        class_match = class_pattern.match(line)
        if class_match:
            current_class = class_match.group(1)

        method_match = method_pattern.search(line)
        if method_match and current_class:
            method = method_match.group(1).upper()
            # Route will be resolved from urls.py — use class name as placeholder
            route = f"/{current_class.lower().replace('view', '').replace('viewset', '')}"
            raw_code = "\n".join(lines[i:min(i+15, len(lines))])

            # Extract params
            params = []
            args_match = re.search(r'def\s+\w+\s*\(([^)]*)\)', line)
            if args_match:
                for arg in args_match.group(1).split(","):
                    arg = arg.strip()
                    if arg and arg not in ("self", "request", "pk", "format"):
                        params.append({"name": arg, "type": "any", "required": True})

            auth_required = any(k in content for k in [
                "IsAuthenticated", "TokenAuthentication", "SessionAuthentication",
                "permission_classes", "authentication_classes"
            ])

            endpoints.append({
                "method": method,
                "route": route,
                "params": params,
                "return_type": "Response (JSON)",
                "auth_required": auth_required,
                "raw_code": raw_code,
                "source_file": os.path.basename(filepath)
            })

    return endpoints