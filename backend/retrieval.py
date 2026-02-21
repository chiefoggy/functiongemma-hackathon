"""
Retrieval: search the corpus (parsed text in cache_dir) by query.
Returns top-k chunks or file paths + snippets for hub tool handlers.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

def _get_cache_dir() -> Path:
    from .indexer import get_cache_dir
    from . import config as library_config
    root = library_config.get_library_root()
    return get_cache_dir(Path(root) if root else None)


def search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search corpus for query. Returns list of { "path", "snippet", "score" }.
    Uses simple substring match for now; can add embeddings later.
    """
    cache_dir = _get_cache_dir()
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.exists():
        return []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    query_lower = query.lower()
    results = []

    for rel_path, safe_name in manifest.items():
        txt_path = cache_dir / safe_name
        if not txt_path.exists():
            continue
        try:
            text = txt_path.read_text(encoding="utf-8", errors="replace")
            if query_lower in text.lower():
                # Extract a snippet around the match
                idx = text.lower().find(query_lower)
                start = max(0, idx - 80)
                end = min(len(text), idx + len(query) + 80)
                snippet = text[start:end].replace("\n", " ")
                if len(snippet) > 300:
                    snippet = snippet[:300] + "..."
                results.append({
                    "path": rel_path,
                    "snippet": snippet,
                    "score": 1.0,
                })
            # Also check line-by-line for partial matches (e.g. "quiz" in a line)
            for line in text.splitlines():
                if query_lower in line.lower() and not any(r["snippet"] == line.strip() for r in results):
                    results.append({
                        "path": rel_path,
                        "snippet": line.strip()[:400],
                        "score": 0.8,
                    })
                    break
        except Exception:
            continue

    # Dedupe by path, sort by score, return top_k
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: -x["score"]):
        if r["path"] in seen:
            continue
        seen.add(r["path"])
        unique.append(r)
        if len(unique) >= top_k:
            break
    return unique
