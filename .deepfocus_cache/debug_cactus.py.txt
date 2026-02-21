
import sys, os
import ctypes
from pathlib import Path

# Setup paths
_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT / "cactus" / "python" / "src"))

from cactus import cactus_init, cactus_rag_query, cactus_get_last_error

cwd = os.getcwd()
weights_path = os.path.join(cwd, "cactus/weights/functiongemma-270m-it")
corpus_dir = os.path.join(cwd, "temp_corpus")

print(f"Initializing model with corpus_dir: {corpus_dir}")
model = cactus_init(weights_path, corpus_dir=corpus_dir, cache_index=True)

if not model:
    print(f"FAILED to init model: {cactus_get_last_error()}")
    sys.exit(1)

print("Model initialized.")

query = "pheasants and rabbits"
print(f"Querying: {query}")
results = cactus_rag_query(model, query, top_k=5)
print(f"Results: {results}")

if not results:
    print(f"Last error: {cactus_get_last_error()}")

# Try a very simple query
query = "lecture"
print(f"Querying: {query}")
results = cactus_rag_query(model, query, top_k=5)
print(f"Results: {results}")
