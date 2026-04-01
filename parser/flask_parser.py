"""
parser/flask_parser.py
Parses Flask route definitions.
Detects: @app.route(), @blueprint.route(), methods=["GET","POST"] etc.
"""

import os
import re
from parser.detect_framework import _find_files, _read_file_safe


def parse_flask(local_path: str) -> list:
    endpoints = []
    py_files = _find_files(local_path, [".py"])

    for fpath in py_files:
        content = _read_file_safe(fpath)
        if not content:
            continue
        if "@app.route" not in content and ".route(" not in content:
            continue

        endpoints.extend(_extract_flask_endpoints(content, fpath))

    print(f"[Flask Parser] Found {len(endpoints)} endpoints")
    return endpoints


def _extract_flask_endpoints(content: str, filepath: str) -> list:
    endpoints = []
    lines = content.split("\n")

    # Match @app.route("/path", methods=["GET","POST"])
    # or @blueprint.route("/path")
    route_pattern = re.compile(
        r'@\w+\.route\s*\(\s*["\']([^"\']+)["\'](?:[^)]*methods\s*=\s*\[([^\]]*)\])?',
        re.IGNORECASE
    )

    for i, line in enumerate(lines):
        match = route_pattern.search(line)
        if match:
            route = match.group(1)
            methods_str = match.group(2)

            # Parse methods list — default is GET if not specified
            methods = ["GET"]
            if methods_str:
                methods = [m.strip().strip('"\'').upper()
                           for m in methods_str.split(",") if m.strip().strip('"\'')]

            # Get raw code snippet
            raw_code = "\n".join(lines[i:min(i+25, len(lines))])

            # Get params and auth from function definition
            params, return_type, auth_required = _get_flask_function_details(lines, i + 1)

            for method in methods:
                endpoints.append({
                    "method": method,
                    "route": route,
                    "params": params,
                    "return_type": return_type,
                    "auth_required": auth_required,
                    "raw_code": raw_code,
                    "source_file": os.path.basename(filepath)
                })

    return endpoints


def _get_flask_function_details(lines: list, start_idx: int):
    params = []
    return_type = "JSON"
    auth_required = False

    for i in range(start_idx, min(start_idx + 5, len(lines))):
        line = lines[i].strip()
        if line.startswith("def "):
            # Check for auth decorators above
            for prev in lines[max(0, start_idx-3):start_idx]:
                if any(k in prev.lower() for k in ["login_required", "token_required", "jwt_required", "auth"]):
                    auth_required = True

            # Extract path params from route (already captured in route string)
            args_match = re.search(r'def\s+\w+\s*\(([^)]*)\)', line)
            if args_match:
                for arg in args_match.group(1).split(","):
                    arg = arg.strip()
                    if arg and arg not in ("self", "cls"):
                        name = arg.split(":")[0].split("=")[0].strip()
                        type_hint = arg.split(":")[1].strip() if ":" in arg else "any"
                        if name:
                            params.append({"name": name, "type": type_hint, "required": True})
            break

    return params, return_type, auth_required