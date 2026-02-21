
import sys, os, json, time
sys.path.insert(0, "cactus/python/src")

if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split('=', 1)
                if len(parts) == 2:
                    key, val = parts
                    os.environ[key.strip()] = val.strip().strip('"\'')

cwd = os.getcwd()
functiongemma_path = os.path.join(cwd, "cactus/weights/functiongemma-270m-it")
whisper_path = os.path.join(cwd, "cactus/weights/whisper-small")

from cactus import cactus_init, cactus_complete, cactus_destroy
from google import genai
from google.genai import types

_whisper_model = None
_cactus_model = None

def transcribe_audio(audio_path: str) -> str:
    """Lazily load Whisper model and transcribe a WAV audio file."""
    global _whisper_model
    from cactus import cactus_transcribe
    if _whisper_model is None:
        _whisper_model = cactus_init(whisper_path)
    return cactus_transcribe(_whisper_model, audio_path)

def generate_cactus(messages, tools):
    """Run function calling on-device via FunctionGemma + Cactus."""
    global _cactus_model
    if _cactus_model is None:
        print(f"DEBUG: Initializing Cactus with {functiongemma_path}")
        _cactus_model = cactus_init(functiongemma_path)
        if _cactus_model is None:
            print("ERROR: cactus_init returned None!")

    cactus_tools = [{
        "type": "function",
        "function": t,
    } for t in tools]

    print(f"DEBUG: Calling cactus_complete with handle {_cactus_model}")
    cactus_system_prompt = (
        "System: You are an OS assistant. Use the provided tools by outputting JSON. "
        "Example: {\"function_calls\": [{\"name\": \"set_dnd\", \"arguments\": {\"status\": true}}]}"
    )
    
    raw_str = cactus_complete(
        _cactus_model,
        [{"role": "system", "content": cactus_system_prompt}] + messages,
        tools=cactus_tools,
        force_tools=True,
        max_tokens=64, # Cap latency on local hallucinations
        stop_sequences=["<|im_end|>", "<end_of_turn>"],
        confidence_threshold=0.0,
    )

    print(f"DEBUG: Cactus Raw: {raw_str}")
    if not raw_str:
        return {"function_calls": [], "total_time_ms": 0, "confidence": 0, "cloud_handoff": True}

    import re
    raw = None
    # Try to extract JSON if it's wrapped in text
    json_match = re.search(r'\{.*\}', raw_str, re.DOTALL)
    if json_match:
        try:
            raw = json.loads(json_match.group(0))
        except (json.JSONDecodeError, TypeError):
            # If extracting from regex match fails, try loading the whole string
            try:
                raw = json.loads(raw_str)
            except (json.JSONDecodeError, TypeError):
                pass # raw remains None
    else:
        # If no regex match, try loading the whole string directly
        try:
            raw = json.loads(raw_str)
        except (json.JSONDecodeError, TypeError):
            pass # raw remains None

    if raw is None:
        return {
            "function_calls": [],
            "total_time_ms": 0,
            "confidence": 0,
            "cloud_handoff": True
        }

    return {
        "function_calls": raw.get("function_calls", []),
        "total_time_ms": raw.get("total_time_ms", 0),
        "confidence": raw.get("confidence", 0),
        "cloud_handoff": raw.get("cloud_handoff", False)
    }

def generate_cactus_text(messages, max_tokens=256):
    """Generate a plain text response locally via Cactus (no tools)."""
    global _cactus_model
    if _cactus_model is None:
        print(f"DEBUG: Initializing Cactus with {functiongemma_path}")
        _cactus_model = cactus_init(functiongemma_path)
        if _cactus_model is None:
            print("ERROR: cactus_init returned None!")

    raw_str = cactus_complete(
        _cactus_model,
        messages,
        tools=None,
        force_tools=False,
        max_tokens=max_tokens,
        stop_sequences=["<|im_end|>", "<end_of_turn>"],
        confidence_threshold=0.0,
    )

    if not raw_str:
        return {"response": "", "total_time_ms": 0, "confidence": 0, "cloud_handoff": True}

    try:
        raw = json.loads(raw_str)
    except (json.JSONDecodeError, TypeError):
        return {"response": raw_str.strip(), "total_time_ms": 0, "confidence": 0, "cloud_handoff": False}

    return {
        "response": raw.get("response") or "",
        "total_time_ms": raw.get("total_time_ms", 0),
        "confidence": raw.get("confidence", 0),
        "cloud_handoff": raw.get("cloud_handoff", False),
    }

def generate_cloud(messages, tools):
    """Run function calling via Gemini Cloud API."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Missing GEMINI_API_KEY environment variable.")
        return {"function_calls": [], "total_time_ms": 0}

    client = genai.Client(api_key=api_key)

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

    system_instruction = "You are a helpful Learning Assistant for students. Use tools to search their course materials (library) and provide synthesized answers from their notes."
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        # Ensure content is a string
        content = m["content"] if isinstance(m["content"], str) else str(m["content"])
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=content)]))
    
    start_time = time.time()

    # Only include tools if they are provided
    config_args = {
        "system_instruction": system_instruction,
    }
    if tools:
        config_args["tools"] = gemini_tools

    try:
        gemini_response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(**config_args),
        )

        total_time_ms = (time.time() - start_time) * 1000
        function_calls = []
        if gemini_response.candidates:
            for candidate in gemini_response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.function_call:
                            function_calls.append({
                                "name": part.function_call.name,
                                "arguments": dict(part.function_call.args),
                            })
        return {
            "response": gemini_response.text if gemini_response.candidates else "",
            "function_calls": function_calls,
            "total_time_ms": total_time_ms
        }
    except Exception as e:
        print(f"CLOUD ERROR: {e}")
        return {"function_calls": [], "total_time_ms": 0}

def generate_hybrid(messages, tools, default_threshold=0.85):
    """
    Learning Assistant Hybrid routing: route search queries locally if possible, 
    otherwise use cloud for general conversation or deep synthesis.
    """
    content = " ".join([m["content"].lower() for m in messages if m["role"] == "user"])
    words = set(content.split())
    
    # We only have search_hub now
    tool_keywords = {
        "search_hub": ["syllabus", "quiz", "timeline", "assignment", "due", "date", "summary", "notes", "lecture", "course", "exam", "test", "reading", "material"],
    }
    
    # Check if this sounds like a library query
    is_library_query = any(kw in content for kw in tool_keywords["search_hub"])
    
    # If it's a library query, try local first
    if is_library_query:
        local = generate_cactus(messages, tools)
        if local.get("function_calls") and local.get("confidence", 0) >= 0.5:
            local["source"] = "on-device (search)"
            return local

    # For general questions (like 2+2) or failed local search, use cloud
    cloud = generate_cloud(messages, tools)
    cloud["source"] = "cloud (conversation)"
    return cloud

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
