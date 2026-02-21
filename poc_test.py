#!/usr/bin/env python3
"""
POC: Test both FunctionGemma (local) and Gemini (cloud) DIRECTLY,
bypassing the web server, routing, and conversation history.

Usage:
  source cactus/venv/bin/activate
  python3 poc_test.py

It'll ask you to pick: 1 = local only, 2 = cloud only, 3 = both. This will show exactly what each model outputs for "hi", "stock price of AAPL", and "weather in SF".
"""
import sys, os, json, time

# Load .env
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split('=', 1)
                if len(parts) == 2:
                    os.environ[parts[0].strip()] = parts[1].strip().strip('"\'')

sys.path.insert(0, "cactus/python/src")

# ─── Test tools ───
TOOLS = [
    {
        "name": "get_stock_price",
        "description": "Get the current stock price for a given ticker symbol.",
        "parameters": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "The stock ticker symbol, e.g., AAPL."}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a location.",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "City name"}},
            "required": ["location"],
        },
    },
]

SINGLE_TOOL = [TOOLS[0]]  # Just stock price

# ─── Test cases ───
TEST_CASES = [
    ("Simple greeting", [{"role": "user", "content": "hi"}]),
    ("Stock price query", [{"role": "user", "content": "What is the stock price of AAPL?"}]),
    ("Weather query", [{"role": "user", "content": "What's the weather in San Francisco?"}]),
]

SEPARATOR = "=" * 60

# ─── Test 1: FunctionGemma (local via cactus) ───
def test_local():
    print(f"\n{SEPARATOR}")
    print("  TEST 1: FunctionGemma (Local via Cactus)")
    print(SEPARATOR)

    try:
        from cactus import cactus_init, cactus_complete
    except ImportError as e:
        print(f"❌ Cannot import cactus: {e}")
        print("   Make sure you ran: source cactus/venv/bin/activate")
        return

    model_path = os.path.join(os.getcwd(), "cactus/weights/functiongemma-270m-it")
    if not os.path.isdir(model_path):
        print(f"❌ Model not found at: {model_path}")
        print("   Run: cactus download google/functiongemma-270m-it --reconvert")
        return

    print(f"Initializing model from {model_path}...")
    model = cactus_init(model_path)
    if model is None:
        print("❌ cactus_init returned None!")
        return
    print(f"✅ Model initialized (handle: {model})\n")

    cactus_tools = [{"type": "function", "function": t} for t in TOOLS]

    for label, messages in TEST_CASES:
        print(f"\n--- {label}: \"{messages[0]['content']}\" ---")
        start = time.time()
        try:
            raw = cactus_complete(
                model,
                messages,
                tools=cactus_tools,
                force_tools=True,
                max_tokens=64,
                stop_sequences=["<|im_end|>", "<end_of_turn>"],
                confidence_threshold=0.0,
            )
            elapsed = (time.time() - start) * 1000
            print(f"  Time: {elapsed:.0f}ms")
            print(f"  Raw output: {repr(raw)}")

            if raw:
                try:
                    import re
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        print(f"  Parsed JSON: {json.dumps(parsed, indent=2)}")
                    else:
                        print(f"  ⚠️  No JSON found in output")
                except json.JSONDecodeError:
                    print(f"  ⚠️  Could not parse as JSON")
            else:
                print(f"  ⚠️  Empty output")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    from cactus import cactus_destroy
    cactus_destroy(model)
    print(f"\n✅ Local model test complete")


# ─── Test 2: Gemini (cloud) ───
def test_cloud():
    print(f"\n{SEPARATOR}")
    print("  TEST 2: Gemini Flash (Cloud)")
    print(SEPARATOR)

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key or api_key == "YOUR_KEY_HERE":
        print("❌ GEMINI_API_KEY not set or still placeholder!")
        print("   Edit .env and set your real key, then re-run.")
        return

    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        print(f"❌ Cannot import google-genai: {e}")
        print("   Run: pip install google-genai")
        return

    print(f"API key: {api_key[:8]}...{api_key[-4:]}")
    client = genai.Client(api_key=api_key)

    # Test A: Simple text generation (no tools)
    print(f"\n--- Test A: Simple text (no tools) ---")
    try:
        start = time.time()
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hello in exactly 5 words.",
        )
        elapsed = (time.time() - start) * 1000
        print(f"  Time: {elapsed:.0f}ms")
        print(f"  Response: {resp.text}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # Test B: Tool calling
    gemini_tools = [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        k: types.Schema(type=v["type"].upper(), description=v.get("description", ""))
                        for k, v in t["parameters"]["properties"].items()
                    },
                    required=t["parameters"].get("required", []),
                ),
            )
            for t in TOOLS
        ])
    ]

    for label, messages in TEST_CASES:
        print(f"\n--- {label}: \"{messages[0]['content']}\" ---")
        contents = " ".join(m["content"] for m in messages if m["role"] == "user")
        start = time.time()
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction="You are a helpful assistant. Use tools when appropriate.",
                    tools=gemini_tools,
                ),
            )
            elapsed = (time.time() - start) * 1000
            print(f"  Time: {elapsed:.0f}ms")

            function_calls = []
            text_parts = []
            if resp.candidates:
                for candidate in resp.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.function_call:
                                function_calls.append({
                                    "name": part.function_call.name,
                                    "arguments": dict(part.function_call.args),
                                })
                            if part.text:
                                text_parts.append(part.text)

            if function_calls:
                print(f"  Tool calls: {json.dumps(function_calls, indent=2)}")
            if text_parts:
                print(f"  Text: {' '.join(text_parts)}")
            if not function_calls and not text_parts:
                print(f"  ⚠️  No output from Gemini")

        except Exception as e:
            print(f"  ❌ Error: {e}")

    print(f"\n✅ Cloud model test complete")


# ─── Main ───
if __name__ == "__main__":
    print(SEPARATOR)
    print("  POC: Direct Model Testing")
    print(f"  GEMINI_API_KEY: {'SET' if os.environ.get('GEMINI_API_KEY') else 'NOT SET'}")
    print(f"  CACTUS_API_KEY: {'SET' if os.environ.get('CACTUS_API_KEY') else 'NOT SET'}")
    print(SEPARATOR)

    print("\nWhich test to run?")
    print("  1 = Local (FunctionGemma via Cactus)")
    print("  2 = Cloud (Gemini Flash)")
    print("  3 = Both")
    choice = input("\nChoice [3]: ").strip() or "3"

    if choice in ("1", "3"):
        test_local()
    if choice in ("2", "3"):
        test_cloud()

    print(f"\n{SEPARATOR}")
    print("  DONE")
    print(SEPARATOR)
