
import sys
sys.path.insert(0, "cactus/python/src")
functiongemma_path = "cactus/weights/functiongemma-270m-it"

import json, os, time

# Load basic .env file if it exists
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip().strip('"\'')

from cactus import cactus_init, cactus_complete, cactus_destroy
from google import genai
from google.genai import types


def generate_cactus(messages, tools):
    """Run function calling on-device via FunctionGemma + Cactus."""
    model = cactus_init(functiongemma_path)

    cactus_tools = [{
        "type": "function",
        "function": t,
    } for t in tools]

    raw_str = cactus_complete(
        model,
        [{"role": "system", "content": "You are a helpful assistant that can use tools."}] + messages,
        tools=cactus_tools,
        force_tools=True,
        max_tokens=256,
        stop_sequences=["<|im_end|>", "<end_of_turn>"],
    )

    cactus_destroy(model)

    try:
        raw = json.loads(raw_str)
    except json.JSONDecodeError:
        return {
            "function_calls": [],
            "total_time_ms": 0,
            "confidence": 0,
        }

    return {
        "function_calls": raw.get("function_calls", []),
        "total_time_ms": raw.get("total_time_ms", 0),
        "confidence": raw.get("confidence", 0),
    }


def generate_cloud(messages, tools):
    """Run function calling via Gemini Cloud API."""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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
            for t in tools
        ])
    ]

    contents = [m["content"] for m in messages if m["role"] == "user"]

    start_time = time.time()

    gemini_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(tools=gemini_tools),
    )

    total_time_ms = (time.time() - start_time) * 1000

    function_calls = []
    for candidate in gemini_response.candidates:
        for part in candidate.content.parts:
            if part.function_call:
                function_calls.append({
                    "name": part.function_call.name,
                    "arguments": dict(part.function_call.args),
                })

    return {
        "function_calls": function_calls,
        "total_time_ms": total_time_ms,
    }


def generate_hybrid(messages, tools, default_threshold=0.85):
    """Deep-Focus Hybrid routing: intelligently route OS actions locally, cloud for deep cognition."""
    content = " ".join([m["content"].lower() for m in messages if m["role"] == "user"])

    # =====================================================================
    # STRATEGY 1: Semantic OS/Action Escaping
    # =====================================================================
    # If the user asks for deep summary cognition or heavy text extraction, instantly route to Cloud.
    # The 270M parameters of FunctionGemma cannot handle complex NLP summarization effectively.
    cognition_keywords = ["summarize", "draft", "email", "transcript", "analyze", "explain"]
    requires_cognition = any(kw in content for kw in cognition_keywords)
    
    if requires_cognition:
        cloud = generate_cloud(messages, tools)
        cloud["source"] = "cloud (deep cognition)"
        return cloud

    # =====================================================================
    # STRATEGY 2: Syntactic Complexity Bypass (Latency Protection)
    # =====================================================================
    # Compound multi-step queries paralyze the local model's tool mapping logic.
    complex_indicators = [" and ", "also", "then", ", ", "after", "before"]
    is_compound = any(ind in content for ind in complex_indicators)
    is_long = len(content.split()) > 25
    
    if (is_compound and len(tools) > 1) or is_long:
        cloud = generate_cloud(messages, tools)
        cloud["source"] = "cloud (syntactic bypass)"
        return cloud

    # =====================================================================
    # STRATEGY 3: Dynamic Edge Authority Auditing (Privacy First)
    # =====================================================================
    # Boot the local macOS model for OS-level triggers.
    local = generate_cactus(messages, tools)

    # Scale our functional trust based on toolset complexity
    if len(tools) == 1:
        dynamic_threshold = 0.65 
    elif len(tools) == 2:
        dynamic_threshold = 0.80
    else:
        dynamic_threshold = default_threshold

    if local["confidence"] >= dynamic_threshold:
        local["source"] = "on-device"
        return local

    # Handoff securely if local macOS execution fails the confidence audit
    cloud = generate_cloud(messages, tools)
    cloud["source"] = "cloud (fallback)"
    cloud["local_confidence"] = local["confidence"]
    cloud["total_time_ms"] += local["total_time_ms"] # Latency penalty applied
    return cloud


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file (WAV). Stub: implement with cactus_transcribe + Whisper model for real transcription."""
    return "[Transcription not configured. Use cactus transcribe or add Whisper model to enable.]"


def print_result(label, result):
    """Pretty-print a generation result."""
    print(f"\n=== {label} ===\n")
    if "source" in result:
        print(f"Source: {result['source']}")
    if "confidence" in result:
        print(f"Confidence: {result['confidence']:.4f}")
    if "local_confidence" in result:
        print(f"Local confidence (below threshold): {result['local_confidence']:.4f}")
    print(f"Total time: {result['total_time_ms']:.2f}ms")
    for call in result["function_calls"]:
        print(f"Function: {call['name']}")
        print(f"Arguments: {json.dumps(call['arguments'], indent=2)}")


############## Example usage ##############

if __name__ == "__main__":
    tools = [{
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name",
                }
            },
            "required": ["location"],
        },
    }]

    messages = [
        {"role": "user", "content": "What is the weather in San Francisco?"}
    ]

    on_device = generate_cactus(messages, tools)
    print_result("FunctionGemma (On-Device Cactus)", on_device)

    cloud = generate_cloud(messages, tools)
    print_result("Gemini (Cloud)", cloud)

    hybrid = generate_hybrid(messages, tools)
    print_result("Hybrid (On-Device + Cloud Fallback)", hybrid)
