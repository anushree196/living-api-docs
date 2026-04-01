"""
rag/embedder.py
Handles text embedding using all-MiniLM-L6-v2 via sentence-transformers.
Embeds endpoint docs and stores them into FAISS.
"""

import os
import numpy as np
from sentence_transformers import SentenceTransformer

# Singleton model — loaded once, reused across all calls
_model = None


def get_model() -> SentenceTransformer:
    """Load and cache the embedding model."""
    global _model
    if _model is None:
        print("[Embedder] Loading all-MiniLM-L6-v2...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[Embedder] Model loaded.")
    return _model


def embed_text(text: str) -> np.ndarray:
    """
    Embed a single string and return a numpy array of shape (384,).
    all-MiniLM-L6-v2 produces 384-dimensional embeddings.
    """
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return embedding.astype(np.float32)


def embed_texts(texts: list) -> np.ndarray:
    """
    Embed a list of strings.
    Returns numpy array of shape (len(texts), 384).
    """
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.astype(np.float32)


def make_doc_chunk(method: str, route: str, doc_content: str) -> str:
    """
    Create a structured text chunk for embedding.
    Combines method + route + doc so retrieval is context-aware.
    """
    return f"ENDPOINT: {method.upper()} {route}\n\n{doc_content}"


def embed_endpoint(store, method: str, route: str, doc_content: str, repo_url: str):
    """
    Embed an endpoint's generated doc and add it to the FAISS store.
    Also updates the metadata list in the store.
    """
    if store is None:
        return

    chunk = make_doc_chunk(method, route, doc_content)
    embedding = embed_text(chunk)

    # Add to FAISS index
    import faiss
    store["index"].add(np.expand_dims(embedding, axis=0))

    # Store metadata so we can retrieve by index position
    store["metadata"].append({
        "method": method.upper(),
        "route": route,
        "doc_content": doc_content,
        "repo_url": repo_url
    })

    # Persist updated store to disk
    from rag.vector_store import save_store
    save_store(store, repo_url)