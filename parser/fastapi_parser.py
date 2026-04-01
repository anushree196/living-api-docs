"""
parser/fastapi_parser.py
Parses FastAPI route definitions from Python source files.
Detects: @app.get, @app.post, @router.get, etc.
Extracts: method, route, params, return type, auth hints, raw code snippet.
"""

import os
import re
import ast

from parser.detect_framework import _find_files, _read_file_safe


# HTTP method decorators FastAPI uses
FASTAPI_METHODS = ["get", "post", "put", "patch", "delete", "head", "options"]


def parse_fastapi(local_path: str) -> list:
    """
    Parse all FastAPI endpoints in the repo.
    Returns list of endpoint dicts.
    """
    endpoints = []
    py_files = _find_files(local_path, [".py"])

    for fpath in py_files:
        content = _read_file_safe(fpath)
        if not content:
            continue

        # Only process files that look like they have FastAPI routes
        if not any(f"@app.{m}" in content or f"@router.{m}" in content
                   for m in FASTAPI_METHODS):
            continue

        file_endpoints = _extract_endpoints_from_file(content, fpath)
        endpoints.extend(file_endpoints)

    print(f"[FastAPI Parser] Found {len(endpoints)} endpoints")
    return endpoints


def _extract_endpoints_from_file(content: str, filepath: str) -> list:
    """Extract all endpoints from a single Python file using regex + AST."""
    endpoints = []
    lines = content.split("\n")

    # Pattern: @app.METHOD("route") or @router.METHOD("route")
    decorator_pattern = re.compile(
        r'@(?:app|router)\.(' + "|".join(FASTAPI_METHODS) + r')\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )

    i = 0
    while i < len(lines):
        match = decorator_pattern.search(lines[i])
        if match:
            method = match.group(1).upper()
            route = match.group(2)

            # Grab the function block (decorator + def + body up to next decorator)
            raw_code_lines = []
            j = i
            while j < len(lines):
                raw_code_lines.append(lines[j])
                # Stop at next decorator or end of function (simple heuristic)
                if j > i and lines[j].startswith("@"):
                    break
                if j > i + 1 and lines[j].strip() == "" and j + 1 < len(lines) and lines[j + 1].startswith("@"):
                    break
                j += 1

            raw_code = "\n".join(raw_code_lines[:30])  # cap at 30 lines

            # Extract function signature for params
            params, return_type, auth_required = _extract_function_details(
                lines, i + 1  # start scanning from next line after decorator
            )

            endpoints.append({
                "method": method,
                "route": route,
                "params": params,
                "return_type": return_type,
                "auth_required": auth_required,
                "raw_code": raw_code,
                "source_file": os.path.basename(filepath)
            })

        i += 1

    return endpoints


def _extract_function_details(lines: list, start_idx: int):
    """
    Extract parameters, return type, and auth hints from a function definition.
    Scans from start_idx for the 'def ...' line.
    """
    params = []
    return_type = "JSON"
    auth_required = False

    for i in range(start_idx, min(start_idx + 5, len(lines))):
        line = lines[i].strip()

        if line.startswith("def ") or line.startswith("async def "):
            # Extract return type annotation
            return_match = re.search(r'\)\s*->\s*([^:]+):', line)
            if return_match:
                return_type = return_match.group(1).strip()

            # Extract function arguments
            args_match = re.search(r'def\s+\w+\s*\(([^)]*)\)', line)
            if args_match:
                args_str = args_match.group(1)
                params = _parse_params(args_str)

            # Auth hints
            if any(k in line.lower() for k in ["token", "depends", "security", "oauth", "apikey"]):
                auth_required = True

            break

    return params, return_type, auth_required


def _parse_params(args_str: str) -> list:
    """Parse function argument string into list of param dicts."""
    params = []
    if not args_str.strip():
        return params

    # Split by comma, handle type annotations
    for arg in args_str.split(","):
        arg = arg.strip()
        if not arg or arg in ("self", "cls", "request", "response", "db", "session"):
            continue

        # Skip Depends() injections — these are framework internals
        if "Depends(" in arg or "Security(" in arg:
            auth_required = True
            continue

        # Parse name: type = default
        name = arg.split(":")[0].split("=")[0].strip()
        type_hint = ""
        if ":" in arg:
            type_part = arg.split(":")[1].split("=")[0].strip()
            type_hint = type_part

        if name and not name.startswith("*"):
            params.append({
                "name": name,
                "type": type_hint or "any",
                "required": "=" not in arg
            })

    return params