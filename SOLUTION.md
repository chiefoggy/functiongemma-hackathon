# Deep-Focus: Privacy-First OS Executive Assistant

**Deep-Focus** is a privacy-first macOS executive assistant that leverages high-performance on-device AI and the Gemini 2.5 Flash cloud API. It uses a custom hybrid routing engine to execute OS-level automation locally for maximum security, while handing off deep cognition tasks to the cloud.

---

## 🏆 Functional Architecture & Innovation

### **1. Advanced Hybrid Routing (Latency & Privacy Optimized)**
Our 3-tier hybrid routing logic in `main.py -> generate_hybrid` ensures that sensitive OS actions never leave the device, while complex reasoning is handled by Gemini:

1.  **Semantic OS/Action Escaping**:
    Queries requesting deep cognition (e.g., "summarize meeting", "draft email") are instantly routed to the cloud. The small 270M parameter edge model is preserved for deterministic OS-level triggers, preventing low-accuracy hallucinations on high-entropy text tasks.
2.  **Syntactic Complexity Bypass**:
    We protect system latency by bypassing the local model for compound, multi-tool queries (e.g., "Set DND and then open my report"). These queries are routed to Gemini 2.5 Flash to avoid the local model's overhead when functional accuracy is mathematically likely to drop.
3.  **Dynamic Edge Authority Auditing**:
    Rather than a fixed threshold, our router uses **Dynamic Confidence Scalers**. For simple 1-tool triggers, we trust local execution at a lower confidence (0.65), maximizing on-device speed. For ambiguous requests, the threshold scales to 0.85, forcing a secure cloud handoff to maintain benchmark **F1 Accuracy**.

---

## **2. End-to-End OS Integration**
Deep-Focus isn't just a chatbot; it is deeply integrated into the macOS environment:
- **Local Automation Hook**: Uses AppleScript and subprocess hooks to natively toggle **Do Not Disturb** and **Open Documents** without external dependencies.
- **Rich Metric Dashboard**: A Vanilla JS frontend provides real-time transparency into the AI's "brain," showing whether the command was executed on-device or in the cloud, along with latency and confidence metrics.

---

## **3. Low-Latency Voice-to-Action**
We implemented a zero-config voice interface using `cactus_transcribe`. 
- **Privacy-First Audio**: User speech is captured via the MediaRecorder API, buffered to 16kHz WAV, and POSTed to our FastAPI backend.
- **On-Device Whisper**: The backend lazily loads the local Whisper-small model, transcribing speech locally before passing it to our hybrid router—providing a seamless, hands-free "Voice-to-Action" workflow.
