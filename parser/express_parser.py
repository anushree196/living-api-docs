"""
parser/express_parser.py
Parses Express.js route definitions from JavaScript files.
Detects: app.get(), app.post(), router.get(), router.post(), etc.
"""

import os
import re
from parser.detect_framework import _find_files, _read_file_safe

EXPRESS_METHODS = ["get", "post", "put", "patch", "delete", "head", "options", "all"]


def parse_express(local_path: str) -> list:
    endpoints = []
    js_files = _find_files(local_path, [".js", ".ts"])

    for fpath in js_files:
        content = _read_file_safe(fpath)
        if not content:
            continue

        # Only process files with Express route definitions
        if not any(f".{m}(" in content for m in EXPRESS_METHODS):
            continue

        endpoints.extend(_extract_express_endpoints(content, fpath))

    print(f"[Express Parser] Found {len(endpoints)} endpoints")
    return endpoints


def _extract_express_endpoints(content: str, filepath: str) -> list:
    endpoints = []
    lines = content.split("\n")

    # Match: app.get("/route", ...) or router.post("/route", ...)
    route_pattern = re.compile(
        r'(?:app|router)\.' +
        r'(' + "|".join(EXPRESS_METHODS) + r')' +
        r'\s*\(\s*["\`\']([^"\`\']+)["\`\']',
        re.IGNORECASE
    )

    for i, line in enumerate(lines):
        match = route_pattern.search(line)
        if match:
            method = match.group(1).upper()
            route = match.group(2)

            # Get raw code block
            raw_code = "\n".join(lines[i:min(i + 20, len(lines))])

            # Extract path params from route string e.g. /users/:id
            path_params = re.findall(r':(\w+)', route)
            params = [{"name": p, "type": "string", "required": True} for p in path_params]

            # Check for auth middleware in line or surrounding lines
            surrounding = "\n".join(lines[max(0, i-2):min(i+3, len(lines))])
            auth_required = any(k in surrounding.lower() for k in [
                "authmiddleware", "verifyttoken", "authenticate",
                "passport", "jwt", "bearertoken", "requireauth"
            ])

            # Extract query params from req.query references in next 10 lines
            body_snippet = "\n".join(lines[i:min(i+10, len(lines))])
            query_params = re.findall(r'req\.query\.(\w+)', body_snippet)
            body_params = re.findall(r'req\.body\.(\w+)', body_snippet)

            for qp in query_params:
                params.append({"name": qp, "type": "string", "required": False, "in": "query"})
            for bp in body_params:
                params.append({"name": bp, "type": "any", "required": True, "in": "body"})

            endpoints.append({
                "method": method,
                "route": route,
                "params": params,
                "return_type": "JSON",
                "auth_required": auth_required,
                "raw_code": raw_code,
                "source_file": os.path.basename(filepath)
            })

    return endpoints