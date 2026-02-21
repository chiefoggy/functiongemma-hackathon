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

def _validate_corpus_dir(cache_dir: Path) -> tuple[bool, str]:
    """Validate that corpus directory exists and has content files."""
    if not cache_dir.exists():
        return False, f"Corpus directory does not exist: {cache_dir}"
    
    if not cache_dir.is_dir():
        return False, f"Corpus path is not a directory: {cache_dir}"
    
    # Check for manifest.json
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.exists():
        return False, "Manifest file not found. Please re-index your library."
    
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest:
            return False, "Manifest is empty. Please re-index your library."
        
        # Check if at least some corpus files exist
        corpus_files = [f for f in cache_dir.glob("*.txt") if f.name != "manifest.json"]
        if not corpus_files:
            return False, "No corpus files found. Please re-index your library."
        
        # Check if files have actual content (not just metadata)
        content_found = False
        for txt_file in corpus_files[:5]:  # Sample first 5 files
            content = txt_file.read_text(encoding="utf-8", errors="replace")
            # Check if content has more than just path/name metadata
            if len(content) > 200 and "\n\n" in content:
                content_found = True
                break
        
        if not content_found:
            return False, "Corpus files appear to have no content. Please re-index with content extraction enabled."
        
        return True, f"Corpus validated: {len(manifest)} files indexed, {len(corpus_files)} corpus files found"
    except Exception as e:
        return False, f"Error validating corpus: {e}"


def _get_rag_model():
    """Lazily initialize a Cactus model for RAG with validation."""
    global _rag_model, _rag_model_root
    from . import config as library_config
    from cactus import cactus_init, cactus_get_last_error
    import os
    
    root = library_config.get_library_root()
    if not root:
        return None

    if _rag_model is None or _rag_model_root != root:
        # Use the same weights as main.py
        cwd = os.getcwd()
        weights_path = os.path.join(cwd, "cactus/weights/functiongemma-270m-it")
        cache_dir = _get_cache_dir()
        
        # Validate corpus before initializing
        is_valid, validation_msg = _validate_corpus_dir(cache_dir)
        if not is_valid:
            print(f"WARNING: Corpus validation failed: {validation_msg}")
            print("RAG queries may not work properly. Please re-index your library.")
        else:
            print(f"DEBUG: {validation_msg}")
        
        print(f"DEBUG: Initializing RAG model with corpus_dir: {cache_dir}")
        _rag_model = cactus_init(weights_path, corpus_dir=str(cache_dir), cache_index=True)
        
        if _rag_model is None:
            error_msg = cactus_get_last_error()
            print(f"ERROR: Failed to initialize RAG model. Error: {error_msg}")
            print(f"  Weights path: {weights_path}")
            print(f"  Corpus dir: {cache_dir}")
            return None
        
        _rag_model_root = root
        print(f"DEBUG: RAG model initialized successfully")
        
    return _rag_model

def verify_corpus() -> Dict[str, Any]:
    """Verify corpus status and return diagnostic information."""
    cache_dir = _get_cache_dir()
    is_valid, msg = _validate_corpus_dir(cache_dir)
    
    result = {
        "valid": is_valid,
        "message": msg,
        "corpus_dir": str(cache_dir),
        "exists": cache_dir.exists(),
    }
    
    if cache_dir.exists():
        manifest_path = cache_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                result["files_indexed"] = len(manifest)
                result["manifest_exists"] = True
            except:
                result["manifest_exists"] = False
        
        corpus_files = list(cache_dir.glob("*.txt"))
        result["corpus_files_count"] = len([f for f in corpus_files if f.name != "manifest.json"])
        
        # Sample a file to check content
        sample_files = [f for f in corpus_files if f.name != "manifest.json"][:3]
        if sample_files:
            sample_content = sample_files[0].read_text(encoding="utf-8", errors="replace")
            result["sample_file_size"] = len(sample_content)
            result["has_content"] = len(sample_content) > 200 and "\n\n" in sample_content
    
    return result


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
        from cactus import cactus_rag_query, cactus_get_last_error
        try:
            print(f"DEBUG: Executing RAG query: '{query}' (top_k={top_k})")
            raw_results = cactus_rag_query(model, query, top_k=top_k)
            
            if raw_results:
                print(f"DEBUG: RAG query returned {len(raw_results)} results")
                for i, r in enumerate(raw_results):
                    snippet = r.get("text", "").strip()
                    score = r.get("score", 0.9)
                    
                    if snippet:
                        # Try to extract file path from snippet if it contains path metadata
                        path = "Library Document"
                        if "path:" in snippet:
                            try:
                                path_line = [line for line in snippet.split("\n") if line.startswith("path:")][0]
                                path = path_line.replace("path:", "").strip()
                            except:
                                pass
                            
                            # Clean up snippet: remove path/name metadata lines if they're at the start
                            lines = snippet.split("\n")
                            cleaned_lines = []
                            skip_metadata = True
                            for line in lines:
                                if skip_metadata and (line.startswith("path:") or line.startswith("name:")):
                                    continue
                                skip_metadata = False
                                cleaned_lines.append(line)
                            
                            cleaned_snippet = "\n".join(cleaned_lines).strip()
                            if not cleaned_snippet:
                                cleaned_snippet = snippet  # Fallback to original if cleaning removed everything
                            
                            # Limit snippet length for better readability
                            if len(cleaned_snippet) > 1000:
                                cleaned_snippet = cleaned_snippet[:1000] + "..."
                            
                            results.append({
                                "path": path,
                                "snippet": cleaned_snippet,
                                "score": score,
                            })
                            seen_snippets.add(cleaned_snippet.lower())
                            print(f"DEBUG: Result {i+1}: path={path[:50]}, score={score:.3f}, snippet_len={len(cleaned_snippet)}")
                    else:
                        print(f"DEBUG: Result {i+1}: Empty snippet, skipping")
            else:
                error_msg = cactus_get_last_error()
                if error_msg:
                    print(f"WARNING: RAG SEMANTIC SEARCH returned no results. Error: {error_msg}")
                else:
                    print(f"INFO: RAG SEMANTIC SEARCH returned no results for query: '{query}'")
                    print("DEBUG: This might indicate the corpus is empty or the query doesn't match any content.")
        except Exception as e:
            print(f"RAG SEMANTIC SEARCH ERROR: {e}")
            import traceback
            traceback.print_exc()

    # 2. Keyword Fallback (Substring / Token-based)
    if len(results) < top_k:
        print(f"DEBUG: Semantic search returned {len(results)} results, using keyword fallback to reach {top_k}")
        try:
            cache_dir = _get_cache_dir()
            manifest_path = cache_dir / "manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                print(f"DEBUG: Keyword search scanning {len(manifest)} files in manifest")
                
                # Tokenize query
                import re
                words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 2]
                if not words: words = [query.lower()]
                
                # Simple stopword list
                stopwords = {"the", "and", "for", "with", "from", "that", "this", "query", "search", "what", "is", "of", "in", "to", "a", "an"}
                keywords = [w for w in words if w not in stopwords]
                if not keywords: keywords = words
                
                print(f"DEBUG: Keyword search using keywords: {keywords}")
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
                        
                        # Extract a better snippet around the keyword match
                        # Try to get a paragraph or section around the match
                        start = max(0, first_idx - 300)
                        end = min(len(text), first_idx + 500)
                        
                        # Try to find sentence boundaries for cleaner snippets
                        snippet_text = text[start:end]
                        
                        # Remove path/name metadata if present
                        lines = snippet_text.split("\n")
                        cleaned_lines = []
                        skip_metadata = True
                        for line in lines:
                            if skip_metadata and (line.startswith("path:") or line.startswith("name:")):
                                continue
                            skip_metadata = False
                            cleaned_lines.append(line)
                        
                        snippet_text = "\n".join(cleaned_lines)
                        
                        # Clean up whitespace
                        snippet = " ".join(snippet_text.split())
                        if len(snippet) > 800:
                            snippet = snippet[:800] + "..."
                        
                        if snippet.lower() not in seen_snippets and len(snippet) > 50:
                            matches.append({
                                "path": rel_path,
                                "snippet": snippet,
                                "score": score,
                                "found_count": found_count
                            })
                            seen_snippets.add(snippet.lower())

                # Sort matches by found_count then score
                matches.sort(key=lambda x: (-x["found_count"], -x["score"]))
                print(f"DEBUG: Keyword search found {len(matches)} matches")
                for m in matches:
                    if len(results) >= top_k: break
                    results.append({
                        "path": m["path"],
                        "snippet": m["snippet"],
                        "score": m["score"]
                    })
            else:
                print(f"DEBUG: Manifest file not found at {manifest_path}")
        except Exception as e:
            print(f"ERROR: KEYWORD SEARCH failed: {e}")
            import traceback
            traceback.print_exc()

    final_results = sorted(results, key=lambda x: -x["score"])[:top_k]
    print(f"DEBUG: Search complete. Returning {len(final_results)} results (requested {top_k})")
    return final_results
