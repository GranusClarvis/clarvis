"""ChromaDB factory — single point of instantiation for clients and embeddings.

Consolidates PersistentClient creation and ONNX embedding function loading
so that all callers share the same instances (no duplicate model loads,
no scattered chromadb imports).

Production callers:
  - ClarvisBrain (clarvis/brain/__init__.py) — main + local singletons
  - LiteBrain (scripts/lite_brain.py) — per-agent, isolated data dirs

Standalone package (clarvis-db VectorStore) and test fixtures are intentionally
left unchanged — they have their own lifecycle.

Usage:
    from clarvis.brain.factory import get_chroma_client, get_embedding_function

    client = get_chroma_client("/path/to/data")     # singleton per path
    embed  = get_embedding_function(use_onnx=True)   # singleton ONNX model
"""

import os
import threading

import chromadb

# --- Singleton registries (thread-safe) ---

_lock = threading.Lock()
_clients: dict[str, chromadb.ClientAPI] = {}  # abs-path -> client
_onnx_embed = None  # singleton embedding function


def get_chroma_client(path: str, *, telemetry: bool = False) -> chromadb.ClientAPI:
    """Return a PersistentClient for *path*, creating one if needed.

    The same client instance is returned for the same absolute path,
    avoiding duplicate SQLite locks and memory overhead.
    """
    abspath = os.path.abspath(path)
    if abspath in _clients:
        return _clients[abspath]

    with _lock:
        # Double-check after acquiring lock
        if abspath in _clients:
            return _clients[abspath]

        os.makedirs(abspath, exist_ok=True)
        settings = chromadb.Settings(anonymized_telemetry=telemetry)
        client = chromadb.PersistentClient(path=abspath, settings=settings)
        _clients[abspath] = client
        return client


def get_embedding_function(use_onnx: bool = True):
    """Return the ONNX MiniLM embedding function (singleton) or None.

    When *use_onnx* is True the model is loaded once and reused across
    all callers — ClarvisBrain, LiteBrain, etc.
    """
    if not use_onnx:
        return None

    global _onnx_embed
    if _onnx_embed is not None:
        return _onnx_embed

    with _lock:
        if _onnx_embed is not None:
            return _onnx_embed
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        _onnx_embed = ONNXMiniLM_L6_V2()
        return _onnx_embed


def reset_singletons() -> None:
    """Clear cached clients and embedding function (for tests only)."""
    global _onnx_embed
    with _lock:
        _clients.clear()
        _onnx_embed = None
