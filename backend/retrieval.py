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


_rag_model = None
_rag_model_root: Optional[str] = None


def reset_rag_model() -> None:
    """Reset cached RAG model so it can be rebuilt for a new corpus."""
    global _rag_model, _rag_model_root
    _rag_model = None
    _rag_model_root = None

def _get_rag_model():
    """Lazily initialize a Cactus model for RAG."""
    global _rag_model, _rag_model_root
    from . import config as library_config
    from cactus import cactus_init
    import os
    
    root = library_config.get_library_root()
    if not root:
        return None

    if _rag_model is None or _rag_model_root != root:
        # Use the same weights as main.py
        cwd = os.getcwd()
        weights_path = os.path.join(cwd, "cactus/weights/functiongemma-270m-it")
        cache_dir = _get_cache_dir()
        
        print(f"DEBUG: Initializing RAG model with corpus_dir: {cache_dir}")
        _rag_model = cactus_init(weights_path, corpus_dir=str(cache_dir), cache_index=True)
        _rag_model_root = root
        
    return _rag_model

def search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search corpus for query using a hybrid approach:
    1. Try semantic search via Cactus engine.
    2. Fallback/Supplement with keyword-based substring search.
    Returns list of { "path", "snippet", "score" }.
    """
    results = []
    seen_snippets = set()

    # 1. Semantic Search (Cactus)
    model = _get_rag_model()
    if model:
        from cactus import cactus_rag_query
        try:
            raw_results = cactus_rag_query(model, query, top_k=top_k)
            for r in raw_results:
                snippet = r.get("text", "").strip()
                if snippet:
                    results.append({
                        "path": "Library Document", # We'll improve this if possible
                        "snippet": f"...{snippet}...",
                        "score": r.get("score", 0.9),
                    })
                    seen_snippets.add(snippet.lower())
        except Exception as e:
            print(f"RAG SEMANTIC SEARCH ERROR: {e}")

    # 2. Keyword Fallback (Substring / Token-based)
    if len(results) < top_k:
        try:
            cache_dir = _get_cache_dir()
            manifest_path = cache_dir / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                
                # Tokenize query
                import re
                words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 2]
                if not words: words = [query.lower()]
                
                # Simple stopword list
                stopwords = {"the", "and", "for", "with", "from", "that", "this", "query", "search", "what", "is", "of", "in", "to", "a", "an"}
                keywords = [w for w in words if w not in stopwords]
                if not keywords: keywords = words
                
                matches = []
                for rel_path, safe_name in manifest.items():
                    txt_path = cache_dir / safe_name
                    if not txt_path.exists(): continue
                    
                    text = txt_path.read_text(encoding="utf-8", errors="replace")
                    text_lower = text.lower()
                    
                    # Score by how many keywords were found
                    found_count = 0
                    first_idx = -1
                    for kw in keywords:
                        if kw in text_lower:
                            found_count += 1
                            if first_idx == -1: first_idx = text_lower.find(kw)
                    
                    if found_count > 0:
                        # Success! Found at least one keyword.
                        # Calculate a score based on ratio of words found
                        score = 0.5 + (found_count / len(keywords)) * 0.3
                        
                        start = max(0, first_idx - 200)
                        end = min(len(text), first_idx + 400)
                        snippet = text[start:end].replace("\n", " ").strip()
                        
                        if snippet.lower() not in seen_snippets:
                            matches.append({
                                "path": rel_path,
                                "snippet": f"...{snippet}...",
                                "score": score,
                                "found_count": found_count
                            })
                            seen_snippets.add(snippet.lower())

                # Sort matches by found_count then score
                matches.sort(key=lambda x: (-x["found_count"], -x["score"]))
                for m in matches:
                    if len(results) >= top_k: break
                    results.append({
                        "path": m["path"],
                        "snippet": m["snippet"],
                        "score": m["score"]
                    })
        except Exception as e:
            print(f"KEYWORD SEARCH ERROR: {e}")

    return sorted(results, key=lambda x: -x["score"])[:top_k]
