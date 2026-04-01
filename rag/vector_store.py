"""
rag/vector_store.py
FAISS vector store — create, save, load, update.
One store per repo, persisted to disk under data/faiss_index/.
Store structure:
  {
    "index": faiss.IndexFlatIP,   # Inner product (cosine on normalized vecs)
    "metadata": [                  # Parallel list to FAISS index
      { method, route, doc_content, repo_url },
      ...
    ]
  }
"""

import os
import json
import faiss
import numpy as np

FAISS_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "faiss_index")
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


def _repo_key(repo_url: str) -> str:
    """Convert repo URL to a safe directory name."""
    return repo_url.rstrip("/").replace(".git", "").split("github.com/")[-1].replace("/", "_")


def _store_paths(repo_url: str):
    """Return (index_path, metadata_path) for a repo."""
    key = _repo_key(repo_url)
    base = os.path.join(FAISS_BASE_DIR, key)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "index.faiss"), os.path.join(base, "metadata.json")


def create_store() -> dict:
    """Create a fresh empty FAISS store."""
    index = faiss.IndexFlatIP(EMBEDDING_DIM)  # Inner product = cosine on normalised vecs
    return {"index": index, "metadata": []}


def save_store(store: dict, repo_url: str):
    """Persist FAISS index and metadata to disk."""
    index_path, meta_path = _store_paths(repo_url)
    faiss.write_index(store["index"], index_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(store["metadata"], f, indent=2)


def load_store(repo_url: str) -> dict:
    """
    Load FAISS store from disk for a repo.
    Returns None if no store exists yet (first run).
    """
    index_path, meta_path = _store_paths(repo_url)

    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        return None

    try:
        index = faiss.read_index(index_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        return {"index": index, "metadata": metadata}
    except Exception as e:
        print(f"[VectorStore] Failed to load store for {repo_url}: {e}")
        return None


def get_or_create_store(repo_url: str) -> dict:
    """Load existing store or create a new one."""
    store = load_store(repo_url)
    if store is None:
        store = create_store()
    return store


def update_endpoint_in_store(store: dict, method: str, route: str,
                              new_doc: str, repo_url: str):
    """
    Update an existing endpoint's embedding in the store.
    FAISS doesn't support in-place updates, so we rebuild the index
    by removing old entry and adding new one.
    """
    from rag.embedder import embed_text, make_doc_chunk

    method = method.upper()

    # Find and remove old entry
    new_metadata = []
    kept_embeddings = []

    for i, meta in enumerate(store["metadata"]):
        if meta["method"] == method and meta["route"] == route:
            continue  # Skip old entry
        new_metadata.append(meta)

    # If we removed something, rebuild index from remaining metadata
    if len(new_metadata) < len(store["metadata"]):
        new_index = faiss.IndexFlatIP(EMBEDDING_DIM)
        if new_metadata:
            chunks = [make_doc_chunk(m["method"], m["route"], m["doc_content"])
                      for m in new_metadata]
            from sentence_transformers import SentenceTransformer
            from rag.embedder import embed_texts
            embeddings = embed_texts(chunks)
            new_index.add(embeddings)
        store["index"] = new_index
        store["metadata"] = new_metadata

    # Now add updated entry
    chunk = make_doc_chunk(method, route, new_doc)
    embedding = embed_text(chunk)
    store["index"].add(np.expand_dims(embedding, axis=0))
    store["metadata"].append({
        "method": method,
        "route": route,
        "doc_content": new_doc,
        "repo_url": repo_url
    })

    save_store(store, repo_url)