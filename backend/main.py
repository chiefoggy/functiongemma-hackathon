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

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- REPO PATH SETUP ---
# Ensure we can import from the root 'main.py'
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from fastapi.responses import JSONResponse
from main import generate_hybrid, generate_cactus, generate_cloud, transcribe_audio
from backend import config as library_config
from backend.indexer import run_index, get_status as get_index_status
from backend.retrieval import search as retrieval_search, reset_rag_model

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
conversation_history = []
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
def handle_search_hub(query: str, force_local: bool = False) -> Dict[str, Any]:
    """Logic: Retrieve snippets locally, then synthesize a response."""
    print(f"DEBUG: Handling search_hub for query: {query}")
    results = retrieval_search(query, top_k=5)
    
    if not results:
        print("DEBUG: No results found in retrieval.")
        return {
            "type": "text", 
            "data": "I couldn't find anything relevant in your library. Try re-indexing your root folder or rephrasing your question.",
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
        "1. Provide a clear, structured, and informative answer.\n"
        "2. Cite the source files (e.g., 'According to Lecture 01...') where possible.\n"
        "3. If the provided context does not contain the answer, say 'I couldn't find the specific answer in your current files, but based on general knowledge...' or state that the information is missing.\n"
        "4. Focus on accuracy and academic tone.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Student's Question: {query}"
    )
    
    if force_local:
        print("DEBUG: Calling generate_cloud for synthesis (force_local; generate_cactus_text not implemented)...")
        reply = generate_cloud([{"role": "user", "content": synthesis_prompt}], [])
        response_text = reply.get("response") or "I found relevant notes but encountered an error while summarizing them locally."
    else:
        print("DEBUG: Calling generate_cloud for synthesis...")
        # We call generate_cloud for the synthesis, but we pass NO tools to avoid an infinite loop
        # Important: passing the synthesis_prompt as a single user message
        reply = generate_cloud([{"role": "user", "content": synthesis_prompt}], [])
        response_text = reply.get("response") or "I found relevant notes but encountered an error while summarizing them."
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
async def put_library_root(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"root": library_config.get_library_root(), "ok": False, "error": "Invalid or missing JSON body"}
    if body is None:
        body = {}
    raw = (body.get("root") or "").strip()
    if not raw:
        return {"root": library_config.get_library_root(), "ok": False, "error": "No path provided"}
    normalized = _normalize_path(raw)
    library_config.set_library_root(normalized)
    return {"root": library_config.get_library_root(), "ok": True}


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

# --- CHAT & HYBRID ROUTING ---

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    global conversation_history
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "response": "Invalid or missing request body. Send JSON: { \"message\": \"your question\", \"force_local\": false }",
                "metrics": None,
                "files_touched": [],
            },
        )
    if data is None:
        data = {}
    user_msg = (data.get("message") or "").strip()
    force_local = data.get("force_local", False)

    if not user_msg:
        return JSONResponse(
            status_code=400,
            content={
                "response": "Message is required. Send a question about your library, stock prices, or calculations.",
                "metrics": None,
                "files_touched": [],
            },
        )

    if user_msg.lower() == "clear":
        conversation_history = []
        return {"response": "Conversation cleared!", "metrics": None, "files_touched": []}

    conversation_history.append({"role": "user", "content": user_msg})

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
        summary_text = ""
        for call in calls:
            name = call["name"]
            args = call["arguments"]
            handler = TOOL_HANDLERS.get(name)
            if handler:
                res = handler(force_local=force_local, **args)
                files_touched.extend(res.get("files_touched", []))
                final_blocks.append(res)
                summary_text += f"\n[Executed {name}]: {res.get('data')}"
            else:
                final_blocks.append({"type": "text", "data": f"Error: Tool {name} not found."})
        conversation_history.append({"role": "assistant", "content": summary_text})
        agent_reply = final_blocks
        return {
            "response": agent_reply,
            "metrics": {
                "source": result.get("source", "unknown"),
                "confidence": result.get("confidence", 0.0),
                "latency_ms": result.get("total_time_ms", 0.0),
            },
            "files_touched": list(dict.fromkeys(files_touched)),
        }
    # No tool called; use response if present, otherwise message
    agent_reply = result.get("response")
    if not agent_reply or not isinstance(agent_reply, str):
        agent_reply = "No response generated."
    conversation_history.append({"role": "assistant", "content": agent_reply})
    return {
        "response": agent_reply,
        "metrics": {
            "source": result.get("source", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "latency_ms": result.get("total_time_ms", 0.0),
        },
        "files_touched": [],
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
