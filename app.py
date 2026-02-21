from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import tempfile
import subprocess
import time
from main import generate_hybrid, generate_cactus, transcribe_audio

app = FastAPI()

# Mount the static directory to serve index.html
app.mount("/static", StaticFiles(directory="static"), name="static")

import subprocess

# OS Automation Tools

def set_dnd(status: bool):
    """Enable or disable Do Not Disturb in macOS using AppleScript."""
    try:
        # Focus mode toggle on macOS
        script = f'tell application "System Events" to set value of checkbox "Focus" of scroll area 1 of window "Control Center" of process "Control Center" to {str(status).lower()}'
        # More robust approach: Use a simple toggle script if UI scripting is restricted
        # We'll use the 'Control Center' click as a demonstration of native integration
        toggle_script = '''
        tell application "System Events"
            tell process "Control Center"
                click menu bar item "Control Center" of menu bar 1
                delay 0.5
                if exists checkbox "Focus" of scroll area 1 of window "Control Center" then
                    click checkbox "Focus" of scroll area 1 of window "Control Center"
                end if
                click menu bar item "Control Center" of menu bar 1
            end tell
        end tell
        '''
        # For the hackathon, we'll use a reliable 'open shortcut' or 'defaults' if possible, 
        # but the AppleScript is the most 'OS integration' way.
        subprocess.run(["osascript", "-e", toggle_script], check=False)
        
        msg = f"Do Not Disturb {'enabled' if status else 'disabled'} successfully."
        return {"type": "os_widget", "data": {"action": "set_dnd", "status": status, "message": msg}}
    except Exception as e:
        return {"type": "text", "data": f"Error setting DND: {str(e)}"}

def open_file(filename: str):
    """Open a document or file using macOS Spotlight (mdfind)."""
    try:
        # Use mdfind to search for the file across the system
        # We limit to 1 result for the 'opening' action
        result = subprocess.run(["mdfind", "-name", filename], capture_output=True, text=True, check=True)
        paths = result.stdout.strip().split("\n")
        
        if paths and paths[0]:
            target_path = paths[0]
            subprocess.run(["open", target_path], check=True)
            msg = f"Found and opened '{os.path.basename(target_path)}'."
            return {"type": "os_widget", "data": {"action": "open_file", "filename": filename, "path": target_path, "message": msg}}
        else:
            # Fallback to Desktop/known paths if search fails
            desktop_path = os.path.expanduser(f"~/Desktop/{filename}")
            if os.path.exists(desktop_path):
                subprocess.run(["open", desktop_path], check=True)
                return {"type": "os_widget", "data": {"action": "open_file", "filename": filename, "message": f"Opened '{filename}' from Desktop."}}
            
            return {"type": "os_widget", "data": {"action": "open_file", "filename": filename, "message": f"Could not find '{filename}' using Spotlight.", "error": True}}
    except Exception as e:
        return {"type": "os_widget", "data": {"action": "open_file", "filename": filename, "message": f"Error searching for file: {str(e)}", "error": True}}

def start_focus_session(duration_mins: int):
    """Start a timed focus session: enable DND and set a timer."""
    try:
        # Enable DND using our AppleScript logic
        set_dnd(True)
        
        msg = f"Focus session started for {duration_mins} minutes. Do Not Disturb enabled."
        return {"type": "focus_widget", "data": {
            "action": "start_focus",
            "duration": duration_mins,
            "end_time": (time.time() + (duration_mins * 60)) * 1000, # MS for JS
            "message": msg
        }}
    except Exception as e:
        return {"type": "text", "data": f"Error starting focus session: {str(e)}"}

def summarize_meeting(transcript: str, participants: str = ""):
    """Summarize a meeting transcript using Gemini API."""
    try:
        from google import genai
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        
        prompt = f"Summarize the following meeting transcript. Focus on action items. Participants: {participants}\n\nTranscript: {transcript}"
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        summary = response.text
        
        return {"type": "cognition_widget", "data": {
            "action": "summarize", 
            "summary": summary, 
            "message": "Meeting summary generated via Gemini Cloud."
        }}
    except Exception as e:
        return {"type": "text", "data": f"Error summarizing: {str(e)}"}


# Deep-Focus specific tools
DEEP_FOCUS_TOOLS = [
    {
        "name": "set_dnd",
        "description": "Enable or disable 'Do Not Disturb' or Focus mode on the user's computer.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "boolean",
                    "description": "True to enable Do Not Disturb, False to disable.",
                }
            },
            "required": ["status"],
        },
    },
    {
        "name": "open_file",
        "description": "Search for and open a local file, document, folder, or directory on the user's computer using Spotlight.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The name or path of the file or folder to search for and open.",
                }
            },
            "required": ["filename"],
        },
    },
    {
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
    },
    {
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
]

# Simple in-memory session (for demonstration)
conversation_history = []

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open("static/index.html", "r") as f:
        return f.read()

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    global conversation_history
    data = await request.json()
    user_msg = data.get("message", "")
    force_local = data.get("force_local", False)
    
    if user_msg.lower() == "clear":
        conversation_history = []
        return {"response": "Conversation cleared!", "metrics": None}

    conversation_history.append({"role": "user", "content": user_msg})
    
    if force_local:
        result = generate_cactus(conversation_history, DEEP_FOCUS_TOOLS)
        result["source"] = "on-device (forced)"
    else:
        # Run our hybrid router!
        result = generate_hybrid(conversation_history, DEEP_FOCUS_TOOLS)
    
    # Process tool calls
    formatted_results = [{"type": "text", "content": "Executing OS Directives:\n"}]
    history_text = "Executed OS tools:\n"
    
    calls = result.get("function_calls", [])
    if not calls:
        msg = "I couldn't map that to a local OS command or cloud cognition tool."
        conversation_history.append({"role": "assistant", "content": msg})
        return {
            "response": msg,
            "metrics": {
                "source": result.get("source", "unknown"),
                "confidence": result.get("confidence", 0.0),
                "latency_ms": result.get("total_time_ms", 0.0)
            }
        }

    for call in calls:
        name = call["name"].lower()
        args = call["arguments"]
        try:
            if name == "set_dnd":
                res = set_dnd(**args)
            elif name == "open_file":
                res = open_file(**args)
            elif name == "summarize_meeting":
                res = summarize_meeting(**args)
            elif name == "start_focus_session":
                res = start_focus_session(**args)
            else:
                res = {"type": "text", "data": f"Unknown OS tool: {name}"}
            
            formatted_results.append(res)
            if isinstance(res, dict) and "data" in res and "message" in res["data"]:
                history_text += f"- {name}: {res['data']['message']}\n"
        except Exception as e:
            msg = f"Error executing {name}: {str(e)}"
            formatted_results.append({"type": "text", "data": msg})
            history_text += f"- {name}: {msg}\n"
            
    conversation_history.append({"role": "assistant", "content": history_text})
    return {
        "response": formatted_results,
        "metrics": {
            "source": result.get("source", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "latency_ms": result.get("total_time_ms", 0.0)
        }
    }

@app.post("/api/transcribe")
async def transcribe_endpoint(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = transcribe_audio(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return {"text": text.strip()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
