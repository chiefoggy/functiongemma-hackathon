
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
    """Generate plain text locally via Cactus (no tools)."""
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
        return {"function_calls": [], "total_time_ms": 0, "response": ""}

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
        content = m["content"] if isinstance(m["content"], str) else str(m["content"])
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=content)]))
    start_time = time.time()

    try:
        gemini_response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=gemini_tools if tools else None
            ),
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
        return {"function_calls": [], "total_time_ms": 0, "response": ""}

import json

def generate_hybrid(messages, tools, default_threshold=0.85):
    """
    Structure + semantic guarded hybrid router.
    Optimized for strict schema adherence without breaking edge cases.
    """
    tool_map = {t["name"]: t for t in tools}

    # -------------------------------------------------
    # Helper: validate tool call structure + semantics
    # -------------------------------------------------
    def validate_calls(result):
        calls = result.get("function_calls", [])

        if not isinstance(calls, list) or len(calls) == 0:
            return False

        for call in calls:
            if not isinstance(call, dict):
                return False

            name = call.get("name")
            args = call.get("arguments")

            # Tool must exist
            if name not in tool_map:
                return False

            if not isinstance(args, dict):
                return False

            schema = tool_map[name].get("parameters", {})
            props = schema.get("properties", {})
            required = schema.get("required", [])

            # 1. Required fields check
            for r in required:
                if r not in args:
                    return False

            # 2. Strict Type & Property Validation
            for k, v in args.items():
                
                # Reject hallucinated parameters not present in the schema
                if k not in props:
                    return False

                expected = props[k].get("type", "").lower()

                # --- Strict Type Validation ---
                # Explicitly block bools from passing as integers/numbers
                if expected == "integer" and (not isinstance(v, int) or isinstance(v, bool)):
                    return False
                if expected == "number" and (not isinstance(v, (int, float)) or isinstance(v, bool)):
                    return False
                if expected == "string" and not isinstance(v, str):
                    return False
                if expected == "boolean" and not isinstance(v, bool):
                    return False
                if expected == "array" and not isinstance(v, list):
                    return False
                if expected == "object" and not isinstance(v, dict):
                    return False

                # --- Enum Validation (Critical for Benchmarks) ---
                if "enum" in props:
                    if v not in props["enum"]:
                        return False

                # --- Targeted Semantic Rules (Fixed) ---
                if isinstance(v, str):
                    # Reject only specific broken model artifacts instead of all brackets/Unicode
                    if "<escape>" in v or "<|endoftext|>" in v:
                        return False

        return True

    # -------------------------------------------------
    # Phase 1: local preview
    # -------------------------------------------------
    local = generate_cactus(messages, tools)

    calls = local.get("function_calls", [])
    response_text = local.get("response", "")
    decode_tokens = local.get("decode_tokens", 0)
    confidence = local.get("confidence", 0)

    # -------------------------------------------------
    # Early cloud routing rules
    # -------------------------------------------------

    # 1. No function calls predicted
    if not calls:
        cloud = generate_cloud(messages, tools)
        cloud["source"] = "cloud (no-call)"
        return cloud

    # 2. Multi-call → cloud (small models are often unstable with parallel calls)
    if len(calls) > 1:
        cloud = generate_cloud(messages, tools)
        cloud["source"] = "cloud (multi-call)"
        return cloud

    # 3. Model generated free text instead of pure function output
    if isinstance(response_text, str) and response_text.strip() != "":
        cloud = generate_cloud(messages, tools)
        cloud["source"] = "cloud (text-generation)"
        return cloud

    # 4. Decode too long → instability (Bumped to a safer threshold)
    if isinstance(decode_tokens, int) and decode_tokens > 128:
        cloud = generate_cloud(messages, tools)
        cloud["source"] = "cloud (long-decode)"
        return cloud

    # 5. Low confidence (Fixed to use the dynamic parameter)
    if confidence < default_threshold:
        cloud = generate_cloud(messages, tools)
        cloud["source"] = f"cloud (low-confidence: {confidence:.2f})"
        cloud["local_confidence"] = confidence  # Keep for debugging metrics
        return cloud

    # 6. Semantic & Schema validation
    if not validate_calls(local):
        cloud = generate_cloud(messages, tools)
        cloud["source"] = "cloud (semantic-reject)"
        return cloud

    # -------------------------------------------------
    # Accept local result
    # -------------------------------------------------
    local["source"] = "on-device"
    return local