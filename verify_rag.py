
import sys, os
from pathlib import Path

# Setup paths
_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

from backend.retrieval import search as retrieval_search
from backend.main import handle_search_hub

path = "/Users/weidong/Downloads/MA1101R Linear Algebra I/AY2018-2019 Semester 1 (Dr Ng Kah Loon _ AP Zhang Lei)/Lecture Notes (Assoc Prof Zhang Lei)"
print(f"Testing RAG on: {path}")

# Note: retrieval depends on library_config.get_library_root()
from backend import config as library_config
library_config.set_library_root(path)

query = "pheasants and rabbits problem"
print(f"\nQuerying: {query}")

try:
    print("Step 1: Testing Retrieval...")
    results = retrieval_search(query, top_k=3)
    print(f"Found {len(results)} results.")
    for i, r in enumerate(results):
        print(f"Result {i+1} (Score: {r['score']}): {r['path']}")
        print(f"Snippet: {r['snippet'][:200]}...")

    print("\nStep 2: Testing Synthesis via handle_search_hub...")
    # This will call generate_cloud
    hub_res = handle_search_hub(query)
    print("\nFinal Synthesis Response:")
    print("-" * 50)
    print(hub_res['data'])
    print("-" * 50)
    print(f"Files touched: {hub_res['files_touched']}")

except Exception as e:
    import traceback
    traceback.print_exc()
