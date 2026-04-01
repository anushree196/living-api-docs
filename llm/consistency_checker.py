"""
llm/consistency_checker.py
The innovation layer — verifies that AI-generated documentation claims
are actually supported by the real source code.
Flags hallucinated features, unsupported auth claims, or fake endpoints.
"""

import re


# Claims that should have matching code evidence
CLAIM_PATTERNS = [
    {
        "claim_keywords": ["oauth", "oauth2", "oauth 2"],
        "code_keywords": ["oauth", "oauth2"],
        "warning": "Documentation mentions OAuth but no OAuth implementation found in source code."
    },
    {
        "claim_keywords": ["jwt", "json web token"],
        "code_keywords": ["jwt", "jsonwebtoken", "pyjwt", "jose"],
        "warning": "Documentation mentions JWT but no JWT library usage found in source code."
    },
    {
        "claim_keywords": ["api key", "apikey", "x-api-key"],
        "code_keywords": ["api_key", "apikey", "x-api-key", "api-key", "API_KEY"],
        "warning": "Documentation mentions API key authentication but no API key handling found in code."
    },
    {
        "claim_keywords": ["rate limit", "rate limiting", "throttl"],
        "code_keywords": ["rate_limit", "throttle", "ratelimit", "slowapi", "express-rate-limit"],
        "warning": "Documentation mentions rate limiting but no rate limit implementation found in code."
    },
    {
        "claim_keywords": ["pagination", "paginate", "page_size", "per_page"],
        "code_keywords": ["paginate", "pagination", "page", "limit", "offset", "cursor"],
        "warning": "Documentation mentions pagination but no pagination logic found in code."
    },
    {
        "claim_keywords": ["cache", "cached", "caching"],
        "code_keywords": ["cache", "redis", "memcache", "lru_cache", "@cache"],
        "warning": "Documentation mentions caching but no cache implementation found in code."
    },
    {
        "claim_keywords": ["websocket", "real-time", "realtime"],
        "code_keywords": ["websocket", "ws", "socket.io", "socketio"],
        "warning": "Documentation mentions WebSocket/real-time but no WebSocket code found."
    },
]


def check_consistency(generated_doc: str, raw_code: str) -> list:
    """
    Cross-reference the generated documentation against actual source code.

    Args:
        generated_doc: The AI-generated markdown documentation string
        raw_code: The actual source code snippet for the endpoint

    Returns:
        List of warning strings. Empty list = all clear.
    """
    warnings = []

    if not generated_doc or not raw_code:
        return warnings

    doc_lower = generated_doc.lower()
    code_lower = raw_code.lower()

    for pattern in CLAIM_PATTERNS:
        # Check if doc mentions this feature
        doc_mentions = any(kw in doc_lower for kw in pattern["claim_keywords"])

        if doc_mentions:
            # Check if code actually implements it
            code_supports = any(kw in code_lower for kw in pattern["code_keywords"])

            if not code_supports:
                warnings.append(pattern["warning"])

    # Additional check: endpoint routes mentioned in docs should match code
    # Extract all routes mentioned in the doc
    doc_routes = re.findall(r'`(/[a-zA-Z0-9/_\-{}\?=&]+)`', generated_doc)
    for doc_route in doc_routes:
        # Skip very short generic routes
        if len(doc_route) <= 1:
            continue
        # Check if this route appears anywhere in the code
        route_base = doc_route.split("{")[0].rstrip("/")
        if route_base and len(route_base) > 3:
            if route_base not in raw_code:
                warnings.append(
                    f"Route `{doc_route}` mentioned in documentation but not clearly found in source code. "
                    f"Please verify this is correct."
                )

    return warnings


def verify_manual_edit(edited_doc: str, raw_code: str) -> list:
    """
    Run consistency check on manually edited documentation.
    Called when a developer edits the draft before approving.
    Returns list of warnings about potentially fabricated claims.
    """
    return check_consistency(edited_doc, raw_code)


def format_warnings_for_display(warnings: list) -> str:
    """Format warnings list as a human-readable string for Streamlit display."""
    if not warnings:
        return ""
    lines = ["⚠️ **Consistency Warnings** — These claims may not be supported by the actual code:\n"]
    for w in warnings:
        lines.append(f"- {w}")
    lines.append("\n*Please review these claims before approving the documentation.*")
    return "\n".join(lines)