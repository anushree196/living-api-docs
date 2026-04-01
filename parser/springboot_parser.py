"""
parser/springboot_parser.py
Parses Spring Boot REST Controller annotations from Java files.
Detects: @RestController, @GetMapping, @PostMapping, @RequestMapping etc.
"""

import os
import re
from parser.detect_framework import _find_files, _read_file_safe

MAPPING_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "PatchMapping": "PATCH",
    "DeleteMapping": "DELETE",
    "RequestMapping": "GET",  # Default; overridden by method= attribute
}


def parse_springboot(local_path: str) -> list:
    endpoints = []
    java_files = _find_files(local_path, [".java"])

    for fpath in java_files:
        content = _read_file_safe(fpath)
        if not content:
            continue

        # Only process Controller files
        if "@RestController" not in content and "@Controller" not in content:
            continue

        endpoints.extend(_extract_spring_endpoints(content, fpath))

    print(f"[Spring Boot Parser] Found {len(endpoints)} endpoints")
    return endpoints


def _extract_spring_endpoints(content: str, filepath: str) -> list:
    endpoints = []
    lines = content.split("\n")

    # Extract class-level base path from @RequestMapping on class
    class_base = ""
    class_mapping = re.search(r'@RequestMapping\s*\(\s*["\']([^"\']+)["\']', content)
    if class_mapping:
        class_base = class_mapping.group(1).rstrip("/")

    # Pattern for method-level mappings
    mapping_pattern = re.compile(
        r'@(' + "|".join(MAPPING_ANNOTATIONS.keys()) + r')\s*\(?\s*(?:value\s*=\s*)?["\']?([^"\')\n]*)["\']?\)?',
        re.IGNORECASE
    )

    for i, line in enumerate(lines):
        match = mapping_pattern.search(line)
        if match:
            annotation = match.group(1)
            route_part = match.group(2).strip().strip('"\'')
            method = MAPPING_ANNOTATIONS.get(annotation, "GET")

            # Handle method= override in @RequestMapping
            if annotation == "RequestMapping":
                method_match = re.search(r'method\s*=\s*RequestMethod\.(\w+)', line)
                if method_match:
                    method = method_match.group(1).upper()

            route = class_base + "/" + route_part.lstrip("/") if route_part else class_base or "/"

            # Get raw code
            raw_code = "\n".join(lines[i:min(i + 20, len(lines))])

            # Extract path variables and request params
            params = []
            # Scan next few lines for method signature
            for j in range(i, min(i + 5, len(lines))):
                if "public" in lines[j] or "private" in lines[j]:
                    # Extract @PathVariable and @RequestParam annotations
                    path_vars = re.findall(r'@PathVariable(?:\([^)]*\))?\s+\w+\s+(\w+)', lines[j])
                    req_params = re.findall(r'@RequestParam(?:\([^)]*\))?\s+\w+\s+(\w+)', lines[j])
                    req_body = re.findall(r'@RequestBody\s+\w+\s+(\w+)', lines[j])

                    for pv in path_vars:
                        params.append({"name": pv, "type": "string", "required": True, "in": "path"})
                    for rp in req_params:
                        params.append({"name": rp, "type": "string", "required": False, "in": "query"})
                    for rb in req_body:
                        params.append({"name": rb, "type": "object", "required": True, "in": "body"})

                    # Extract return type
                    return_match = re.search(r'public\s+(\w+(?:<[^>]+>)?)\s+\w+\s*\(', lines[j])
                    return_type = return_match.group(1) if return_match else "ResponseEntity"
                    break
            else:
                return_type = "ResponseEntity"

            # Check for security annotations
            auth_required = any(k in content for k in [
                "@PreAuthorize", "@Secured", "@RolesAllowed",
                "HttpSecurity", "SecurityConfig", "BearerToken"
            ])

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