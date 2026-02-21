"""
Library config: user-specified root path. In-memory for now; can persist to file/env later.
"""
import os
from pathlib import Path
from typing import Optional

_library_root: Optional[str] = None


def get_library_root() -> Optional[str]:
    """Return the configured library root path (env LIBRARY_ROOT or in-memory)."""
    global _library_root
    env_root = os.environ.get("LIBRARY_ROOT", "").strip()
    if env_root:
        return env_root
    return _library_root


def set_library_root(path: Optional[str]) -> None:
    """Set the library root path (in-memory)."""
    global _library_root
    if path is None:
        _library_root = None
        return
    s = path.strip()
    _library_root = s if s else None
