"""
rag/retriever.py
Retrieves the most relevant old documentation for a given endpoint.
Used to give LLM context about what the doc looked like before,
so it updates rather than rewrites from scratch.
"""

import numpy as np
from rag.embedder import embed_text, make_doc_chunk


def retrieve_old_doc(store: dict, method: str, route: str,
                     top_k: int = 1) -> str:
    """
    Retrieve the old documentation for a specific endpoint.

    Strategy:
    1. First try exact match by method + route in metadata (fastest, most accurate)
    2. Fall back to semantic similarity search via FAISS

    Returns the doc string, or None if not found.
    """
    if store is None or not store["metadata"]:
        return None

    method = method.upper()

    # --- Step 1: Exact match ---
    for meta in store["metadata"]:
        if meta["method"] == method and meta["route"] == route:
            return meta["doc_content"]

    # --- Step 2: Semantic similarity fallback ---
    # Useful when route has changed slightly (e.g., /user/{id} → /users/{id})
    query_text = make_doc_chunk(method, route, "")
    query_embedding = embed_text(query_text)
    query_embedding = np.expand_dims(query_embedding, axis=0)

    index = store["index"]
    if index.ntotal == 0:
        return None

    k = min(top_k, index.ntotal)
    distances, indices = index.search(query_embedding, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(store["metadata"]):
            continue
        meta = store["metadata"][idx]
        results.append({
            "score": float(dist),
            "method": meta["method"],
            "route": meta["route"],
            "doc_content": meta["doc_content"]
        })

    if results:
        best = results[0]
        # Only return if similarity is reasonably high (threshold: 0.5)
        if best["score"] >= 0.5:
            print(f"[Retriever] Found similar doc: {best['method']} {best['route']} "
                  f"(score: {best['score']:.3f})")
            return best["doc_content"]

    return None


def retrieve_similar_docs(store: dict, method: str, route: str,
                          top_k: int = 3) -> list:
    """
    Retrieve top-k similar endpoint docs.
    Used to give LLM examples of how similar endpoints were documented.
    Returns list of doc strings.
    """
    if store is None or not store["metadata"]:
        return []

    query_text = make_doc_chunk(method, route, "")
    query_embedding = embed_text(query_text)
    query_embedding = np.expand_dims(query_embedding, axis=0)

    index = store["index"]
    if index.ntotal == 0:
        return []

    k = min(top_k + 1, index.ntotal)  # +1 to account for self-match
    distances, indices = index.search(query_embedding, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(store["metadata"]):
            continue
        meta = store["metadata"][idx]
        # Skip exact self-match
        if meta["method"] == method.upper() and meta["route"] == route:
            continue
        if float(dist) >= 0.3:
            results.append(meta["doc_content"])

    return results[:top_k]