"""
Deep-Focus Backend: Hybrid Study Hub API
Run from repo root: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

import os
import sys
import uuid
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any
import base64

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware

# --- REPO PATH SETUP ---
# Ensure we can import from the root 'main.py'
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# Import your core logic from the root main.py
from main import generate_hybrid, generate_cactus, generate_cloud, generate_cactus_text, transcribe_audio
from backend import config as library_config
from backend.indexer import run_index, get_status as get_index_status
from backend.retrieval import search as retrieval_search, reset_rag_model, verify_corpus

app = FastAPI(title="Deep-Focus: Privacy-First Study Hub")

# Optional multipart support (upload/transcribe)
try:
    import multipart  # type: ignore
    MULTIPART_OK = True
except Exception:
    MULTIPART_OK = False

# --- CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBAL STATE ---
# Removed global `conversation_history` to prevent cross-user contamination
TOOL_HANDLERS = {}
UPLOADS_DIR = Path(os.environ.get("DEEPFOCUS_UPLOADS_DIR", _REPO_ROOT / "uploads"))

# --- HUB TOOLS DEFINITION ---
HUB_TOOLS = [
    {
        "name": "search_hub",
        "description": "Searches your learning materials (PDFs, notes, code, sheets) for specific info, timelines, or summaries.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The specific question or topic to find in your files."}
            },
            "required": ["query"],
        },
    },
]

# --- TOOL HANDLERS ---
# Added `history` for context and `**kwargs` to prevent hallucination crashes
def handle_search_hub(query: str, history: List[Dict[str, Any]], force_local: bool = False, **kwargs) -> Dict[str, Any]:
    """Logic: Retrieve snippets locally, then synthesize a response."""
    print(f"DEBUG: Handling search_hub for query: '{query}'")
    
    # Verify corpus before searching
    corpus_status = verify_corpus()
    if not corpus_status.get("valid", False):
        warning_msg = corpus_status.get("message", "Corpus validation failed")
        print(f"WARNING: {warning_msg}")
    
    results = retrieval_search(query, top_k=5)
    
    if not results:
        print("DEBUG: No results found in retrieval.")
        # Provide more helpful error message based on corpus status
        if not corpus_status.get("valid", False):
            error_msg = (
                f"I couldn't find anything relevant in your library. "
                f"Corpus validation failed: {corpus_status.get('message', 'Unknown error')}. "
                f"Please re-index your library to ensure content is properly extracted."
            )
        else:
            error_msg = (
                f"I couldn't find anything relevant in your library for '{query}'. "
                f"Try rephrasing your question or re-indexing your root folder."
            )
        return {
            "type": "text", 
            "data": error_msg,
            "files_touched": []
        }
    
    # Filter out placeholders and extract unique paths
    files_touched = list({r["path"] for r in results if r["path"] != "Library Document"})
    context_blocks = []
    for i, r in enumerate(results):
        source = os.path.basename(r['path']) if r['path'] != "Library Document" else f"Result {i+1}"
        context_blocks.append(f"Source: {source}\nContent: {r['snippet']}")
    
    context_text = "\n\n".join(context_blocks)
    
    # Synthesis Prompt: We use the context found locally to generate a smart answer
    synthesis_prompt = (
        "You are an expert academic assistant. Use the following snippets from the student's learning materials to answer the question below. "
        "Guidelines:\n"
        "1. Provide a clear, structured, and informative answer based on the provided context.\n"
        "2. Cite the source files (e.g., 'According to [filename]...') where possible.\n"
        "3. If the provided context does not contain enough information to fully answer the question, say so clearly and indicate what information is missing.\n"
        "4. Focus on accuracy and academic tone.\n"
        "5. Do not make up information that is not in the provided context.\n\n"
        f"Context from library:\n{context_text}\n\n"
        f"Student's Question: {query}\n\n"
        "Please provide a helpful answer based on the context above:"
    )
    
    if force_local:
        # Local-only: return direct excerpts to avoid garbled generation
        response_text = "Here are relevant excerpts from your library:\n\n" + context_text
    else:
        print("DEBUG: Calling generate_cloud for synthesis...")
        # Include conversation history so the model doesn't suffer from context amnesia
        # Filter out any non-dict items and ensure proper format
        clean_history = []
        for msg in history:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                clean_history.append({
                    "role": msg["role"],
                    "content": str(msg["content"])
                })
        
        messages = clean_history + [{"role": "user", "content": synthesis_prompt}]
        reply = generate_cloud(messages, [])
        response_text = reply.get("response")
        
        if not response_text or not response_text.strip():
            # Fallback if cloud generation fails
            response_text = (
                f"I found {len(results)} relevant result(s) in your library, but encountered an error while generating a summary. "
                f"Here are the relevant excerpts:\n\n{context_text}"
            )
        print(f"DEBUG: Synthesis complete. Response length: {len(response_text)}")
    
    return {
        "type": "text",
        "data": response_text,
        "files_touched": files_touched
    }

# Register handlers
TOOL_HANDLERS["search_hub"] = handle_search_hub

# --- HELPER FUNCTIONS ---
def _normalize_path(path: str) -> str:
    if not path: return ""
    return os.path.normpath(os.path.expanduser(path.strip()))

# --- API ENDPOINTS ---

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}

# --- LIBRARY MANAGEMENT ---

@app.get("/api/library/root")
async def get_root():
    return {"root": library_config.get_library_root()}

@app.put("/api/library/root")
async def set_root(request: Request):
    body = await request.json()
    path = _normalize_path(body.get("root", ""))
    library_config.set_library_root(path)
    return {"root": path}

@app.post("/api/library/validate")
async def validate_path(request: Request):
    body = await request.json()
    path_str = _normalize_path(body.get("path", ""))
    
    if not path_str:
        return {"ok": False, "error": "No path provided."}
        
    path = Path(path_str)
    if not path.exists():
        return {"ok": False, "error": "Path does not exist.", "path": path_str}
    if not path.is_dir():
        return {"ok": False, "error": "Path is not a directory.", "path": path_str}
        
    # Count supported files
    from backend.parsers import SUPPORTED_EXTENSIONS
    count = 0
    for p in path.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
            count += 1
            
    return {"ok": True, "file_count": count, "path": path_str}

@app.get("/api/library/suggested-roots")
async def suggested_roots():
    home = Path.home()
    candidates = [
        ("Home", home),
        ("Documents", home / "Documents"),
        ("Desktop", home / "Desktop"),
        ("Downloads", home / "Downloads"),
    ]
    roots = [{"label": label, "path": str(path)} for label, path in candidates if path.exists()]
    return {"roots": roots}

@app.post("/api/library/index")
async def trigger_index():
    root = library_config.get_library_root()
    if not root or not os.path.exists(root):
        raise HTTPException(status_code=400, detail="Valid library root not set.")
    status = run_index(root)
    reset_rag_model()
    return {"ok": True, "status": status}

@app.get("/api/library/status")
async def get_status():
    return get_index_status()

@app.get("/api/library/verify-corpus")
async def verify_corpus_endpoint():
    """Verify that the corpus is properly indexed and ready for RAG queries."""
    return verify_corpus()

if MULTIPART_OK:
    @app.post("/api/library/upload")
    async def upload_library(files: List[UploadFile] = File(...)):
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded.")

        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        upload_root = UPLOADS_DIR / str(uuid.uuid4())
        upload_root.mkdir(parents=True, exist_ok=True)

        saved = 0
        for f in files:
            filename = f.filename or ""
            rel = Path(filename)
            if rel.is_absolute():
                rel = Path(*rel.parts[1:])
            rel = Path(*[p for p in rel.parts if p not in ("..", ".", "")])
            if not rel.parts:
                rel = Path(uuid.uuid4().hex)

            dest = upload_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            content = await f.read()
            dest.write_bytes(content)
            saved += 1

        library_config.set_library_root(str(upload_root))
        status = run_index(str(upload_root))
        reset_rag_model()
        return {"ok": True, "root": str(upload_root), "status": status, "files_saved": saved}
else:
    @app.post("/api/library/upload")
    async def upload_library_unavailable():
        raise HTTPException(status_code=501, detail="Upload requires python-multipart, which is not installed.")

@app.post("/api/library/upload-json")
async def upload_library_json(request: Request):
    body = await request.json()
    files = body.get("files", [])
    if not isinstance(files, list) or not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    upload_root = UPLOADS_DIR / str(uuid.uuid4())
    upload_root.mkdir(parents=True, exist_ok=True)

    saved = 0
    for f in files:
        if not isinstance(f, dict):
            continue
        filename = f.get("path") or f.get("name") or ""
        content_b64 = f.get("content_base64")
        if not content_b64:
            continue

        rel = Path(filename)
        if rel.is_absolute():
            rel = Path(*rel.parts[1:])
        rel = Path(*[p for p in rel.parts if p not in ("..", ".", "")])
        if not rel.parts:
            rel = Path(uuid.uuid4().hex)

        try:
            content = base64.b64decode(content_b64)
        except Exception:
            continue

        dest = upload_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        saved += 1

    if saved == 0:
        raise HTTPException(status_code=400, detail="No files saved.")

    library_config.set_library_root(str(upload_root))
    status = run_index(str(upload_root))
    reset_rag_model()
    return {"ok": True, "root": str(upload_root), "status": status, "files_saved": saved}

# --- CHAT & HYBRID ROUTING ---

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    user_msg = data.get("message", "")
    force_local = data.get("force_local", False)
    
    # State is now passed by the client
    conversation_history = data.get("history", [])

    if user_msg.lower() == "clear":
        return {"response": "History cleared.", "metrics": None, "history": []}

    conversation_history.append({"role": "user", "content": user_msg})

    # If forcing local, bypass tool-calling model and directly run retrieval
    if force_local and library_config.get_library_root():
        res = handle_search_hub(user_msg, history=conversation_history, force_local=True)
        agent_reply = res.get("data", "")
        conversation_history.append({"role": "assistant", "content": agent_reply})
        return {
            "response": agent_reply,
            "history": conversation_history,
            "metrics": {"source": "on-device (retrieval)", "confidence": 1.0, "latency_ms": 0.0},
            "files_touched": res.get("files_touched", []),
        }

    # 1. Get appropriate tools
    tools = HUB_TOOLS if library_config.get_library_root() else []

    # 2. Hybrid Route
    if force_local:
        result = generate_cactus(conversation_history, tools)
        result["source"] = "on-device (forced)"
    else:
        result = generate_hybrid(conversation_history, tools)

    # 3. Handle Function Calls (if any)
    calls = result.get("function_calls", [])
    files_touched = []
    final_blocks = []
    
    if calls:
        for call in calls:
            name = call["name"]
            args = call["arguments"]
            handler = TOOL_HANDLERS.get(name)
            
            if handler:
                # Pass history and unpack arguments
                res = handler(history=conversation_history, force_local=force_local, **args)
                files_touched.extend(res.get("files_touched", []))
                final_blocks.append(res)
            else:
                final_blocks.append({"type": "text", "data": f"Error: Tool {name} not found."})
        
        # Consistent string return type for the frontend
        agent_reply = "\n\n".join([b.get("data", "") for b in final_blocks if b.get("type") == "text"])
        conversation_history.append({"role": "assistant", "content": agent_reply})
    else:
        # No tool called; prefer response, otherwise fall back to a text generation path
        agent_reply = result.get("response")
        if not agent_reply:
            if force_local:
                fallback = generate_cactus_text(conversation_history)
                agent_reply = fallback.get("response") or "No response generated."
            else:
                fallback = generate_cloud(conversation_history, [])
                agent_reply = fallback.get("response") or "No response generated."
        
        # Ensure agent_reply is a string before appending
        if not isinstance(agent_reply, str):
            agent_reply = str(agent_reply)
            
        conversation_history.append({"role": "assistant", "content": agent_reply})

    return {
        "response": agent_reply,
        "history": conversation_history, # Return state to the client
        "metrics": {
            "source": result.get("source", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "latency_ms": result.get("total_time_ms", 0.0),
        },
        "files_touched": list(set(files_touched)),
    }

# --- AUDIO & EXTRAS ---

if MULTIPART_OK:
    @app.post("/api/transcribe")
    async def transcribe(audio: UploadFile = File(...)):
        content = await audio.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            text = transcribe_audio(tmp_path)
            return {"text": text.strip()}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
else:
    @app.post("/api/transcribe")
    async def transcribe_unavailable():
        raise HTTPException(status_code=501, detail="Transcription requires python-multipart, which is not installed.")

# Speech -> action: transcribe then route through chat
if MULTIPART_OK:
    @app.post("/api/speech-action")
    async def speech_action(
        request: Request,
        audio: UploadFile = File(...), 
        force_local: bool = False
    ):
        content = await audio.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            text = transcribe_audio(tmp_path).strip()
            if not text:
                return {"ok": False, "error": "No speech detected.", "text": ""}
            
            # Try to get history from form data if provided
            history = []
            try:
                form_data = await request.form()
                history_str = form_data.get("history", "[]")
                if history_str and history_str != "[]":
                    import json
                    history = json.loads(history_str)
            except Exception as e:
                print(f"DEBUG: Could not parse history from form: {e}")
            
            payload = {"message": text, "force_local": force_local, "history": history}
            fake_request = type("Obj", (), {"json": lambda self: payload})()
            chat_result = await chat_endpoint(fake_request)
            return {"ok": True, "text": text, "chat": chat_result}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
else:
    @app.post("/api/speech-action")
    async def speech_action_unavailable():
        raise HTTPException(status_code=501, detail="Speech actions require python-multipart, which is not installed.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
