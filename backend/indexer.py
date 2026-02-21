"""
Indexer: walk library root, parse supported files, write chunked text to corpus/cache directory.
Exposes run_index() and get_status() for the API.
"""
import os
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

from .parsers import parse_file, SUPPORTED_EXTENSIONS

# In-memory status (replace with file or DB later)
_index_status: Dict[str, Any] = {
    "last_run": None,
    "files_indexed": 0,
    "indexed_files": [],
    "errors": [],
    "library_root": None,
}


def get_cache_dir(library_root: Optional[Path] = None) -> Path:
    """Corpus/cache directory: either DEEPFOCUS_CACHE_DIR or {library_root}/.deepfocus_cache or ./cache."""
    env_cache = os.environ.get("DEEPFOCUS_CACHE_DIR")
    if env_cache:
        return Path(env_cache)
    if library_root:
        return Path(library_root) / ".deepfocus_cache"
    return Path(__file__).resolve().parent.parent / "cache"


def split_text_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Pure Python text chunker mimicking LangChain's CharacterTextSplitter.
    Ensures chunks overlap to preserve semantic context without breaking words.
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        
        if end >= text_len:
            chunks.append(text[start:].strip())
            break
            
        # Try to find a space to avoid cutting words in half
        last_space = text.rfind(' ', start, end)
        if last_space != -1 and last_space > start:
            end = last_space
            
        chunks.append(text[start:end].strip())
        
        # Advance the start pointer, stepping back by the overlap amount.
        # max(start + 1, ...) acts as a failsafe to ensure we always move forward
        # in case a single word is larger than the chunk size minus overlap.
        start = max(start + 1, end - overlap)
        
    return chunks


def run_index(library_root: str) -> Dict[str, Any]:
    """
    Index all supported files under library_root. Write chunked text to cache_dir.
    Returns status dict (last_run, files_indexed, errors).
    """
    global _index_status
    root = Path(library_root)
    
    if not root.is_dir():
        _index_status["errors"] = [f"Not a directory: {library_root}"]
        return _index_status

    cache_dir = get_cache_dir(root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {}
    errors = []
    files_indexed = 0

    all_paths = list(root.rglob("*"))

    for path in all_paths:
        if not path.is_file():
            continue
            
        # FIX: Check parts relative to the root to avoid skipping everything 
        # if the user's library parent directory happens to be hidden.
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
            
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        
        try:
            text = parse_file(path)
            if text is None or not text.strip():
                continue
            
            # Chunk the text using the native Python function
            chunks = split_text_into_chunks(text, chunk_size=1000, overlap=200)
            
            # Create a safe base name for the cache files
            rel = path.relative_to(root)
            safe_base_name = str(rel).replace("/", "_").replace("\\", "_")
            
            chunk_files = []
            for idx, chunk in enumerate(chunks):
                chunk_filename = f"{safe_base_name}_chunk{idx}.txt"
                out_path = cache_dir / chunk_filename
                out_path.write_text(chunk, encoding="utf-8", errors="replace")
                chunk_files.append(chunk_filename)
            
            manifest[str(rel)] = chunk_files
            files_indexed += 1
            
        except Exception as e:
            errors.append(f"{path}: {e}")

    # Write the updated manifest
    manifest_path = cache_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    
    _index_status = {
        "last_run": time.time(),
        "files_indexed": files_indexed,
        "indexed_files": sorted(list(manifest.keys())),
        "errors": errors[:20],
        "library_root": str(root),
    }
    
    return _index_status


def get_status() -> Dict[str, Any]:
    """Return last index run status. Reloads from manifest if needed."""
    global _index_status
    
    # If in-memory status is empty but we have a root, try to reload from manifest
    from .config import get_library_root
    
    root_str = get_library_root()
    if not _index_status["last_run"] and root_str:
        root = Path(root_str)
        cache_dir = get_cache_dir(root)
        manifest_path = cache_dir / "manifest.json"
        
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                _index_status = {
                    "last_run": os.path.getmtime(manifest_path),
                    "files_indexed": len(manifest),
                    "indexed_files": sorted(list(manifest.keys())),
                    "errors": [],
                    "library_root": root_str,
                }
            except Exception:
                pass
                
    return dict(_index_status)