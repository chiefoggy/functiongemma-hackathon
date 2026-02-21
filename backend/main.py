from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# 1. Define the exact structure of the JSON we expect the user to send
class BSRequest(BaseModel):
    text: str

# 2. Create the POST endpoint at /detect
@app.post("/detect")
def detect_bs(request: BSRequest):
    # Grab the text the user sent and make it lowercase for easy checking
    text = request.text.lower()
    
    # 3. A very basic mock BS-detection logic
    corporate_buzzwords = ["synergize", "paradigm", "agile", "roi", "cross-functional"]
    
    # Find which buzzwords are in the user's text
    flagged = [word for word in corporate_buzzwords if word in text]
    
    # 4. If we found garbage jargon, flag it as BS
    if len(flagged) > 0:
        return {
            "is_bs": True,
            "bs_score": 85,  # Arbitrary high score for the test
            "flagged_words": flagged
        }
    
    # 5. Otherwise, pass it as normal text
    return {
        "is_bs": False,
        "bs_score": 0,
        "flagged_words": []
    }

from main import generate_hybrid, generate_cactus, transcribe_audio

from backend import config as library_config
from backend.indexer import run_index, get_status as get_index_status
from backend.retrieval import search as retrieval_search

app = FastAPI(title="Deep-Focus API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Tool implementations ----
def get_stock_price(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        name = info.get("shortName", ticker.upper())
        if price:
            return {"type": "stock_widget", "data": {"ticker": ticker.upper(), "name": name, "price": price}}
        return {"type": "text", "data": f"Could not retrieve the current price for {ticker.upper()}."}
    except Exception as e:
        return {"type": "text", "data": f"Error fetching data for {ticker.upper()}: {str(e)}"}


def get_company_news(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        headlines = [{"title": item["title"], "link": item.get("link", "#")} for item in news[:3] if "title" in item]
        if headlines:
            return {"type": "news_widget", "data": {"ticker": ticker.upper(), "headlines": headlines}}
        return {"type": "text", "data": f"No recent news found for {ticker.upper()}."}
    except Exception as e:
        return {"type": "text", "data": f"Error fetching news for {ticker.upper()}: {str(e)}"}


def calculate_roi(initial_value: float, final_value: float):
    roi = ((final_value - initial_value) / initial_value) * 100
    return f"The Return on Investment (ROI) is {roi:.2f}%."


def get_exchange_rate(base_currency: str, target_currency: str):
    rates = {"USD_EUR": 0.85, "EUR_USD": 1.18, "USD_GBP": 0.75, "GBP_USD": 1.33}
    pair = f"{base_currency.upper()}_{target_currency.upper()}"
    rate = rates.get(pair, 1.0)
    return f"The exchange rate from {base_currency.upper()} to {target_currency.upper()} is {rate}."


def calculate_compound_interest(principal: float, rate: float, years: int):
    amount = principal * (1 + rate / 100) ** years
    return f"The compound interest amount after {years} years is ${amount:.2f}."


def get_crypto_price(symbol: str):
    prices = {"BTC": 60000.0, "ETH": 4000.0, "SOL": 150.0}
    price = prices.get(symbol.upper(), 1000.0)
    return f"The current price for {symbol.upper()} is ${price:.2f}."


def calculate_mortgage_payment(principal: float, annual_rate: float, years: int):
    monthly_rate = annual_rate / 100 / 12
    num_payments = years * 12
    if monthly_rate == 0:
        payment = principal / num_payments
    else:
        payment = principal * (monthly_rate * (1 + monthly_rate) ** num_payments) / (
            (1 + monthly_rate) ** num_payments - 1
        )
    return f"The monthly mortgage payment is ${payment:.2f}."


FINANCE_TOOLS = [
    {"name": "get_stock_price", "description": "Get the current stock price for a given ticker symbol.", "parameters": {"type": "object", "properties": {"ticker": {"type": "string", "description": "The stock ticker symbol, e.g., AAPL."}}, "required": ["ticker"]}},
    {"name": "get_company_news", "description": "Get the latest news headlines for a company.", "parameters": {"type": "object", "properties": {"ticker": {"type": "string", "description": "The stock ticker symbol."}}, "required": ["ticker"]}},
    {"name": "calculate_roi", "description": "Calculate Return on Investment (ROI) given initial and final values.", "parameters": {"type": "object", "properties": {"initial_value": {"type": "number"}, "final_value": {"type": "number"}}, "required": ["initial_value", "final_value"]}},
    {"name": "get_exchange_rate", "description": "Get the exchange rate between two currencies.", "parameters": {"type": "object", "properties": {"base_currency": {"type": "string"}, "target_currency": {"type": "string"}}, "required": ["base_currency", "target_currency"]}},
    {"name": "calculate_compound_interest", "description": "Calculate the compound interest amount.", "parameters": {"type": "object", "properties": {"principal": {"type": "number"}, "rate": {"type": "number"}, "years": {"type": "integer"}}, "required": ["principal", "rate", "years"]}},
    {"name": "get_crypto_price", "description": "Get the current price for a given cryptocurrency symbol.", "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "calculate_mortgage_payment", "description": "Calculate the monthly mortgage payment.", "parameters": {"type": "object", "properties": {"principal": {"type": "number"}, "annual_rate": {"type": "number"}, "years": {"type": "integer"}}, "required": ["principal", "annual_rate", "years"]}},
]

TOOL_HANDLERS = {
    "get_stock_price": get_stock_price,
    "get_company_news": get_company_news,
    "calculate_roi": lambda **kw: {"type": "text", "data": calculate_roi(**kw)},
    "get_exchange_rate": lambda **kw: {"type": "text", "data": get_exchange_rate(**kw)},
    "calculate_compound_interest": lambda **kw: {"type": "text", "data": calculate_compound_interest(**kw)},
    "get_crypto_price": lambda **kw: {"type": "text", "data": get_crypto_price(**kw)},
    "calculate_mortgage_payment": lambda **kw: {"type": "text", "data": calculate_mortgage_payment(**kw)},
}

# Hub tools: search the library corpus (syllabi, timelines, notes)
HUB_TOOLS = [
    {
        "name": "search_hub",
        "description": "Search the user's library (indexed files: PDFs, docs, code, spreadsheets) for a query. Use for questions like 'quiz timeline', 'syllabus summary', 'assignment due dates', or any content in the user's learning materials.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query, e.g. 'quiz timeline' or 'syllabus'"}},
            "required": ["query"],
        },
    },
]


def search_hub(query: str):
    """Handler: search corpus and return text for the model. Includes files_touched for sidebar."""
    results = retrieval_search(query, top_k=5)
    if not results:
        return {"type": "text", "data": "No matching content found in the library. Try indexing files first (set library root and run Index).", "files_touched": []}
    parts = [f"**{r['path']}**: {r['snippet']}" for r in results]
    files_touched = list({r["path"] for r in results})
    return {"type": "text", "data": "\n\n".join(parts), "files_touched": files_touched}


def _search_hub_handler(**kw):
    """Robust handler: accept 'query' or fall back to first string arg."""
    q = kw.get("query") or kw.get("search_query") or kw.get("text") or ""
    if not q:
        # Fallback: use first string value from any key
        for v in kw.values():
            if isinstance(v, str) and v.strip():
                q = v.strip()
                break
    if not q:
        return {"type": "text", "data": "No search query provided. Try asking something like 'Search my library for quiz timeline'."}
    return search_hub(q)

TOOL_HANDLERS["search_hub"] = _search_hub_handler


def get_chat_tools():
    """Tools for chat: finance + hub if library root is set."""
    tools = list(FINANCE_TOOLS)
    if library_config.get_library_root():
        tools = list(HUB_TOOLS) + tools
    return tools


conversation_history = []


@app.get("/health")
def health():
    return {"status": "ok"}


# ---- Library hub API ----
def _normalize_path(path: str) -> str:
    """Strip leading/trailing whitespace only, expand ~, then normpath. Preserves spaces inside path."""
    if not path or not isinstance(path, str):
        return ""
    path = path.strip()
    path = os.path.expanduser(path)
    return os.path.normpath(path)


@app.get("/api/library/root")
def get_library_root():
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


@app.post("/api/library/index")
def trigger_index():
    root = library_config.get_library_root()
    if not root:
        return {"ok": False, "error": "Library root not set"}
    status = run_index(root)
    return {"ok": True, "status": status}


@app.get("/api/library/status")
def library_status():
    return get_index_status()


@app.post("/api/library/validate")
async def validate_path(request: Request):
    """Validate that a path exists and is a directory (path sent in body; if omitted, use current root)."""
    import os
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw = (body.get("path") or "").strip() or library_config.get_library_root() or ""
    if not raw:
        return {"ok": False, "error": "No path provided", "path": ""}
    path = _normalize_path(raw)
    if not os.path.exists(path):
        return {"ok": False, "error": f"Path does not exist (resolved: {path})", "path": path}
    if not os.path.isdir(path):
        return {"ok": False, "error": f"Not a directory (resolved: {path})", "path": path}
    try:
        count = sum(1 for _ in Path(path).rglob("*") if _.is_file())
    except Exception as e:
        return {"ok": False, "error": f"Cannot read directory: {e}", "path": path}
    return {"ok": True, "path": path, "exists": True, "is_dir": True, "file_count": count}


@app.get("/api/library/suggested-roots")
def suggested_roots():
    """Return common machine locations for the user to pick (no typing)."""
    import os
    home = os.path.expanduser("~")
    candidates = [
        ("Home", home),
        ("Documents", os.path.join(home, "Documents")),
        ("Desktop", os.path.join(home, "Desktop")),
        ("Downloads", os.path.join(home, "Downloads")),
    ]
    out = []
    for label, path in candidates:
        if os.path.isdir(path):
            out.append({"label": label, "path": path})
    try:
        cwd = os.getcwd()
        if cwd not in [p["path"] for p in out]:
            out.append({"label": "Current folder", "path": cwd})
    except Exception:
        pass
    return {"roots": out}


@app.post("/api/library/upload")
async def upload_library(files: list[UploadFile] = File("files")):
    """
    Accept a folder of files (from browser folder picker). Save to cache, set as library root, run index.
    """
    import uuid
    if not files:
        return {"ok": False, "error": "No files received"}
    cache_base = _REPO_ROOT / "cache"
    upload_dir = cache_base / f"upload_{uuid.uuid4().hex[:12]}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        if not f.filename or f.filename.startswith("."):
            continue
        safe = f.filename.replace("..", "").lstrip("/")
        path = upload_dir / safe
        path.parent.mkdir(parents=True, exist_ok=True)
        content = await f.read()
        path.write_bytes(content)
    library_config.set_library_root(str(upload_dir))
    status = run_index(str(upload_dir))
    return {"ok": True, "root": str(upload_dir), "status": status, "files_received": len(files)}


@app.post("/api/chat")
async def chat(request: Request):
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

    # CRITICAL: Send only the CURRENT message to the models.
    # The full conversation_history caused models to re-emit old tool results.
    current_messages = [{"role": "user", "content": user_msg}]

    tools = get_chat_tools()
    try:
        if force_local:
            result = generate_cactus(current_messages, tools)
            result["source"] = "on-device (forced)"
        else:
            result = generate_hybrid(current_messages, tools)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        conversation_history.pop()  # rollback
        return JSONResponse(
            status_code=500,
            content={
                "response": f"Backend error during generation: {exc}. Check that cactus is authenticated and the model is downloaded.",
                "metrics": None,
                "files_touched": [],
            },
        )

    calls = result.get("function_calls", [])
    files_touched = []
    if calls:
        blocks = [{"type": "text", "content": "Here are the results:\n"}]
        text_for_history = "Here are the results:\n"
        for c in calls:
            name, args = c["name"], c["arguments"]
            try:
                res = TOOL_HANDLERS.get(name, lambda **_: {"type": "text", "data": "Unknown tool."})(**args)
                if isinstance(res, dict) and res.get("files_touched"):
                    files_touched.extend(res["files_touched"])
                blocks.append(res if isinstance(res, dict) and "type" in res else {"type": "text", "content": str(res)})
                text_for_history += f"- **{name}**: {res.get('data', res) if isinstance(res, dict) else res}\n"
            except Exception as e:
                blocks.append({"type": "text", "content": f"- **{name}**: Error - {e}"})
                text_for_history += f"- **{name}**: Error - {e}\n"
        conversation_history.append({"role": "assistant", "content": text_for_history})
        agent_reply = blocks

        return {
            "is_bs": True,
            "bs_score": 85,  # Arbitrary high score for the test
            "flagged_words": flagged
        }

    # No tool call — try to produce a conversational text reply
    # Priority: 1) local model's text response, 2) Gemini cloud (if not force_local), 3) static fallback
    local_text = (result.get("response") or "").strip()
    text_reply = ""
    text_source = result.get("source", "unknown")

    if local_text:
        # The local model returned a text response — use it directly (no cloud needed)
        text_reply = local_text
        text_source = "on-device (text)"
    elif not force_local:
        # Try Gemini cloud for text generation
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                from google import genai as _genai
                from google.genai import types as _types
                _client = _genai.Client(api_key=api_key)
                _resp = _client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=user_msg,
                    config=_types.GenerateContentConfig(
                        system_instruction="You are Deep-Focus, a helpful macOS executive assistant. Answer the user conversationally. If the user asks something you could use tools for, suggest they try a specific question like 'What is the stock price of AAPL?' or 'Search my library for quiz timeline'.",
                    ),
                )
                text_reply = _resp.text or ""
                text_source = "cloud (text)"
        except Exception as _e:
            err_str = str(_e)
            if "RESOURCE_EXHAUSTED" in err_str:
                text_reply = ""  # fall through to static fallback
            else:
                text_reply = ""
                print(f"CLOUD TEXT ERROR: {_e}")

    if not text_reply:
        text_reply = "I can help with stock prices, calculations, exchange rates, and searching your indexed files. Try asking something like 'What is the stock price of AAPL?' or 'Search my library for quiz timeline'."
        text_source = "static fallback"

    conversation_history.append({"role": "assistant", "content": text_reply})
    return {
        "response": text_reply,
        "metrics": {
            "source": text_source,
            "confidence": result.get("confidence", 0.0),
            "latency_ms": result.get("total_time_ms", 0.0),
        },
        "files_touched": [],
    }


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

