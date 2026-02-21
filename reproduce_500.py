
import sys, os
from pathlib import Path

# Setup paths
_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

# Mock library_config
from backend import config as library_config
from backend.indexer import run_index

path = "/Users/weidong/Downloads/MA1101R Linear Algebra I/AY2018-2019 Semester 1 (Dr Ng Kah Loon _ AP Zhang Lei)/Lecture Notes (Assoc Prof Zhang Lei)"
print(f"Testing indexing on: {path}")

try:
    status = run_index(path)
    print("Indexing finished successfully.")
    print(f"Files indexed: {status['files_indexed']}")
    print(f"Errors: {len(status['errors'])}")
    if status['errors']:
        print("First few errors:")
        for e in status['errors'][:3]:
            print(f"  - {e}")
except Exception as e:
    import traceback
    print("Indexing failed with exception:")
    traceback.print_exc()
