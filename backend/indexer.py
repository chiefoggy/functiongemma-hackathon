"""
Indexer: walk library root, parse supported files, write text to corpus/cache directory.
Exposes run_index() and get_status() for the API.
"""
from pathlib import Path
from typing import Dict, Any, Optional
import json

from .parsers import parse_file, SUPPORTED_EXTENSIONS

# In-memory status (replace with file or DB later)
_index_status: Dict[str, Any] = {
    "last_run": None,
    "files_indexed": 0,
    "errors": [],
    "library_root": None,
}


def get_cache_dir(library_root: Optional[Path] = None) -> Path:
    """Corpus/cache directory: either DEEPFOCUS_CACHE_DIR or {library_root}/.deepfocus_cache or ./cache."""
    import os
    env_cache = os.environ.get("DEEPFOCUS_CACHE_DIR")
    if env_cache:
        return Path(env_cache)
    if library_root:
        return Path(library_root) / ".deepfocus_cache"
    return Path(__file__).resolve().parent.parent / "cache"


def run_index(library_root: str) -> Dict[str, Any]:
    """
    Index all supported files under library_root. Write parsed text to cache_dir.
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

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            text = parse_file(path)
            if text is None or not text.strip():
                continue
            # Store under cache with a safe name (relative path -> single file)
            rel = path.relative_to(root)
            safe_name = str(rel).replace("/", "_").replace("\\", "_")
            if not safe_name.endswith(".txt"):
                safe_name += ".txt"
            out_path = cache_dir / safe_name
            out_path.write_text(text, encoding="utf-8", errors="replace")
            manifest[str(rel)] = safe_name
            files_indexed += 1
        except Exception as e:
            errors.append(f"{path}: {e}")

    (cache_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    import time
    _index_status = {
        "last_run": time.time(),
        "files_indexed": files_indexed,
        "errors": errors[:20],
        "library_root": str(root),
    }
    return _index_status


def get_status() -> Dict[str, Any]:
    """Return last index run status."""
    return dict(_index_status)
