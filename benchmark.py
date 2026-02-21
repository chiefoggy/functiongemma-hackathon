
import sys, os
sys.path.insert(0, "cactus/python/src")
os.environ["CACTUS_NO_CLOUD_TELE"] = "1"

import json
from main import generate_hybrid


############## Tool definitions ##############

TOOL_SET_DND = {
    "name": "set_dnd",
    "description": "Enable or disable 'Do Not Disturb' or Focus mode on the user's computer.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "boolean",
                "description": "Set to true to enable Do Not Disturb, false to disable.",
            }
        },
        "required": ["status"],
    },
}

TOOL_OPEN_FILE = {
    "name": "open_file",
    "description": "Search for and open a local file or document on the user's computer.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The exact filename including extension if provided, or the subject/title of the document to open.",
            }
        },
        "required": ["filename"],
    },
}

TOOL_SUMMARIZE_MEETING = {
    "name": "summarize_meeting",
    "description": "Summarize a meeting transcript, extract action items, and optionally draft follow-up emails.",
    "parameters": {
        "type": "object",
        "properties": {
            "transcript": {
                "type": "string",
                "description": "The text transcript content to be summarized.",
            },
            "participants": {
                "type": "string",
                "description": "Optional list of participants to include in the summary or drafted email.",
            }
        },
        "required": ["transcript"],
    },
}

TOOL_START_FOCUS_SESSION = {
    "name": "start_focus_session",
    "description": "Start a timed focus session on the computer. Enables DND and sets a timer.",
    "parameters": {
        "type": "object",
        "properties": {
            "duration_mins": {
                "type": "integer",
                "description": "The length of the focus session in minutes (e.g., 25 for Pomodoro).",
            }
        },
        "required": ["duration_mins"],
    },
}


############## Benchmark cases ##############

BENCHMARKS = [
    # ===== Easy: 1 tool, direct request =====
    {
        "name": "dnd_on",
        "difficulty": "easy",
        "messages": [{"role": "user", "content": "Turn on Do Not Disturb."}],
        "tools": [TOOL_SET_DND],
        "expected_calls": [{"name": "set_dnd", "arguments": {"status": True}}],
    },
    {
        "name": "dnd_off",
        "difficulty": "easy",
        "messages": [{"role": "user", "content": "Disable focus mode."}],
        "tools": [TOOL_SET_DND],
        "expected_calls": [{"name": "set_dnd", "arguments": {"status": False}}],
    },
    {
        "name": "open_report",
        "difficulty": "easy",
        "messages": [{"role": "user", "content": "Open my Weekly_Report.pdf."}],
        "tools": [TOOL_OPEN_FILE],
        "expected_calls": [{"name": "open_file", "arguments": {"filename": "Weekly_Report.pdf"}}],
    },
    {
        "name": "open_notes",
        "difficulty": "easy",
        "messages": [{"role": "user", "content": "Find and open my project notes."}],
        "tools": [TOOL_OPEN_FILE],
        "expected_calls": [{"name": "open_file", "arguments": {"filename": "project notes"}}],
    },
    {
        "name": "start_focus",
        "difficulty": "easy",
        "messages": [{"role": "user", "content": "Start a 25 minute focus session."}],
        "tools": [TOOL_START_FOCUS_SESSION],
        "expected_calls": [{"name": "start_focus_session", "arguments": {"duration_mins": 25}}],
    },
    # ===== Medium: 2-3 tools, slight ambiguity =====
    {
        "name": "summarize_basic",
        "difficulty": "medium",
        "messages": [{"role": "user", "content": "Summarize this meeting: John talked about the budget for 20 minutes."}],
        "tools": [TOOL_SET_DND, TOOL_SUMMARIZE_MEETING],
        "expected_calls": [{"name": "summarize_meeting", "arguments": {"transcript": "John talked about the budget for 20 minutes."}}],
    },
    {
        "name": "dnd_among_three",
        "difficulty": "medium",
        "messages": [{"role": "user", "content": "I need quiet time, enable Focus mode."}],
        "tools": [TOOL_SET_DND, TOOL_OPEN_FILE, TOOL_SUMMARIZE_MEETING],
        "expected_calls": [{"name": "set_dnd", "arguments": {"status": True}}],
    },
    {
        "name": "open_among_three",
        "difficulty": "medium",
        "messages": [{"role": "user", "content": "Open the project plan document."}],
        "tools": [TOOL_SET_DND, TOOL_OPEN_FILE, TOOL_SUMMARIZE_MEETING],
        "expected_calls": [{"name": "open_file", "arguments": {"filename": "project plan document"}}],
    },

    # ===== Hard: multiple tools needed, multi-call =====
    {
        "name": "dnd_and_open",
        "difficulty": "hard",
        "messages": [{"role": "user", "content": "Turn on Do Not Disturb and also open the budget spreadsheet."}],
        "tools": [TOOL_SET_DND, TOOL_OPEN_FILE, TOOL_SUMMARIZE_MEETING],
        "expected_calls": [
            {"name": "set_dnd", "arguments": {"status": True}},
            {"name": "open_file", "arguments": {"filename": "budget spreadsheet"}},
        ],
    },
    {
        "name": "summarize_and_dnd",
        "difficulty": "hard",
        "messages": [{"role": "user", "content": "Summarize the transcript from today's sync and then enable silent mode."}],
        "tools": [TOOL_SET_DND, TOOL_SUMMARIZE_MEETING],
        "expected_calls": [
            {"name": "summarize_meeting", "arguments": {"transcript": "transcript from today's sync"}},
            {"name": "set_dnd", "arguments": {"status": True}},
        ],
    },
]


def _normalize(v):
    """Normalize a value for comparison."""
    if isinstance(v, str):
        return v.strip().lower()
    return v


def _call_matches(predicted, expected):
    """Check if a predicted call matches an expected call (name + argument values)."""
    if predicted["name"] != expected["name"]:
        return False
    pred_args = predicted.get("arguments", {})
    exp_args = expected.get("arguments", {})
    for key, exp_val in exp_args.items():
        if key not in pred_args:
            return False
        if _normalize(pred_args[key]) != _normalize(exp_val):
            return False
    return True


def compute_f1(predicted_calls, expected_calls):
    """Compute F1 score between predicted and expected function calls."""
    if not predicted_calls and not expected_calls:
        return 1.0
    if not predicted_calls or not expected_calls:
        return 0.0

    matched = 0
    used = set()
    for exp in expected_calls:
        for i, pred in enumerate(predicted_calls):
            if i not in used and _call_matches(pred, exp):
                matched += 1
                used.add(i)
                break

    precision = matched / len(predicted_calls)
    recall = matched / len(expected_calls)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def run_benchmark(benchmarks=None):
    """Run all benchmark cases and print results."""
    if benchmarks is None:
        benchmarks = BENCHMARKS

    total = len(benchmarks)
    results = []
    for i, case in enumerate(benchmarks, 1):
        print(f"[{i}/{total}] Running: {case['name']} ({case['difficulty']})...", end=" ", flush=True)
        result = generate_hybrid(case["messages"], case["tools"])
        f1 = compute_f1(result["function_calls"], case["expected_calls"])
        source = result.get("source", "unknown")
        print(f"F1={f1:.2f} | {result['total_time_ms']:.0f}ms | {source}")
        results.append({
            "name": case["name"],
            "difficulty": case["difficulty"],
            "total_time_ms": result["total_time_ms"],
            "f1": f1,
            "source": source,
            "predicted": result["function_calls"],
            "expected": case["expected_calls"],
        })

    print("\n=== Benchmark Results ===\n")
    print(f"  {'#':>2} | {'Difficulty':<10} | {'Name':<28} | {'Time (ms)':>10} | {'F1':>5} | Source")
    print(f"  {'--':>2}-+-{'-'*10}-+-{'-'*28}-+-{'-'*10}-+-{'-'*5}-+-{'-'*20}")
    for i, r in enumerate(results, 1):
        print(f"  {i:>2} | {r['difficulty']:<10} | {r['name']:<28} | {r['total_time_ms']:>10.2f} | {r['f1']:>5.2f} | {r['source']}")

    print(f"\n--- Summary ---")
    for difficulty in ["easy", "medium", "hard"]:
        group = [r for r in results if r["difficulty"] == difficulty]
        if not group:
            continue
        avg_f1 = sum(r["f1"] for r in group) / len(group)
        avg_time = sum(r["total_time_ms"] for r in group) / len(group)
        on_device = sum(1 for r in group if r["source"] == "on-device")
        cloud = len(group) - on_device
        print(f"  {difficulty:<8} avg F1={avg_f1:.2f}  avg time={avg_time:.2f}ms  on-device={on_device}/{len(group)} cloud={cloud}/{len(group)}")

    avg_f1 = sum(r["f1"] for r in results) / len(results)
    avg_time = sum(r["total_time_ms"] for r in results) / len(results)
    total_time = sum(r["total_time_ms"] for r in results)
    on_device_total = sum(1 for r in results if r["source"] == "on-device")
    cloud_total = len(results) - on_device_total
    print(f"  {'overall':<8} avg F1={avg_f1:.2f}  avg time={avg_time:.2f}ms  total time={total_time:.2f}ms")
    print(f"           on-device={on_device_total}/{len(results)} ({100*on_device_total/len(results):.0f}%)  cloud={cloud_total}/{len(results)} ({100*cloud_total/len(results):.0f}%)")

    # Total score
    score = compute_total_score(results)
    print(f"\n{'='*50}")
    print(f"  TOTAL SCORE: {score:.1f}%")
    print(f"{'='*50}")

    return results


def compute_total_score(results):
    """
    Compute a total score from 0-100% as a weighted sum across difficulty levels.

    Components (per difficulty level):
      - F1 score (50%): accuracy of tool calls
      - Time score (25%): faster is better, capped at 500ms baseline
      - On-device ratio (25%): higher on-device usage is better

    Difficulty weights:
      - easy: 20%
      - medium: 30%
      - hard: 50%
    """
    difficulty_weights = {"easy": 0.20, "medium": 0.30, "hard": 0.50}
    time_baseline_ms = 500  # anything under this gets full marks

    total_score = 0
    for difficulty, weight in difficulty_weights.items():
        group = [r for r in results if r["difficulty"] == difficulty]
        if not group:
            continue

        avg_f1 = sum(r["f1"] for r in group) / len(group)
        avg_time = sum(r["total_time_ms"] for r in group) / len(group)
        on_device_ratio = sum(1 for r in group if r["source"] == "on-device") / len(group)

        time_score = max(0, 1 - avg_time / time_baseline_ms)

        level_score = (0.60 * avg_f1) + (0.15 * time_score) + (0.25 * on_device_ratio)
        total_score += weight * level_score

    return total_score * 100


if __name__ == "__main__":
    run_benchmark()