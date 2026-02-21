"""
Indexer: walk library root, list supported files, write path/name to corpus/cache.
Fast: no content parsing (no PDF/DOCX extraction) so indexing does not hang or crash.
Exposes run_index() and get_status() for the API.
"""
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import json

from .parsers import SUPPORTED_EXTENSIONS

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
    Index supported files under library_root by path/name only (no content parsing).
    Fast: no PDF/DOCX extraction, so no hangs or crashes. Search matches on file path and name.
    Clears existing cache before rebuilding.
    Returns status dict (last_run, files_indexed, errors).
    """
    global _index_status
    root = Path(library_root)
    if not root.is_dir():
        _index_status["errors"] = [f"Not a directory: {library_root}"]
        return _index_status

    cache_dir = get_cache_dir(root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for f in cache_dir.iterdir():
        try:
            f.unlink()
        except OSError:
            pass
    manifest = {}
    errors = []
    files_indexed = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            rel = path.relative_to(root)
            rel_str = str(rel).replace("\\", "/")
            name_hash = hashlib.sha256(rel_str.encode("utf-8")).hexdigest()[:16]
            safe_name = f"{name_hash}.txt"
            # Store only path and filename so search can match; no content parsing
            content = f"path: {rel_str}\nname: {path.name}\n"
            (cache_dir / safe_name).write_text(content, encoding="utf-8", errors="replace")
            manifest[rel_str] = safe_name
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
