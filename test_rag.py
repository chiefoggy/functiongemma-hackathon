#!/usr/bin/env python3
"""
Test script for RAG functionality.
Usage: python test_rag.py [library_root] [query]
"""

import sys
import os
from pathlib import Path

# Setup paths
_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

from backend.retrieval import search as retrieval_search, verify_corpus, reset_rag_model
from backend import config as library_config

def main():
    if len(sys.argv) > 1:
        library_root = sys.argv[1]
        library_config.set_library_root(library_root)
        print(f"Set library root to: {library_root}")
    else:
        library_root = library_config.get_library_root()
        if not library_root:
            print("ERROR: No library root set. Usage: python test_rag.py [library_root] [query]")
            sys.exit(1)
        print(f"Using library root: {library_root}")
    
    # Verify corpus
    print("\n=== Corpus Verification ===")
    corpus_status = verify_corpus()
    print(f"Valid: {corpus_status.get('valid', False)}")
    print(f"Message: {corpus_status.get('message', 'N/A')}")
    print(f"Corpus dir: {corpus_status.get('corpus_dir', 'N/A')}")
    print(f"Files indexed: {corpus_status.get('files_indexed', 0)}")
    print(f"Corpus files: {corpus_status.get('corpus_files_count', 0)}")
    
    if not corpus_status.get("valid", False):
        print("\nWARNING: Corpus validation failed. RAG queries may not work properly.")
        print("Please re-index your library.")
        sys.exit(1)
    
    # Reset RAG model to ensure fresh initialization
    reset_rag_model()
    
    # Test queries
    queries = []
    if len(sys.argv) > 2:
        queries = [sys.argv[2]]
    else:
        queries = [
            "lecture",
            "assignment",
            "syllabus",
            "quiz",
        ]
    
    print("\n=== Testing RAG Queries ===")
    for query in queries:
        print(f"\nQuery: '{query}'")
        print("-" * 60)
        
        try:
            results = retrieval_search(query, top_k=3)
            print(f"Found {len(results)} results:")
            
            for i, r in enumerate(results, 1):
                print(f"\nResult {i}:")
                print(f"  Path: {r['path']}")
                print(f"  Score: {r.get('score', 0):.3f}")
                snippet = r.get('snippet', '')
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                print(f"  Snippet: {snippet}")
        except Exception as e:
            print(f"ERROR: Query failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
