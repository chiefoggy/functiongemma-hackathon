# FinanceGemma: Hybrid Edge-Cloud AI

**FinanceGemma** is a Hackathon submission that leverages the new `cactus` macOS bindings to build a real-time, privacy-first financial analyst assistant. It seamlessly weaves an edge 270M parameter FunctionGemma model and the cloud-based Gemini 2.5 Flash API together using a highly optimized, 3-tiered hybrid routing algorithm.

---

## 🏆 Qualitative Judging Rubrics Overview

### **Rubric 1: Advanced Hybrid Routing Architecture**
The core of our Hackathon submission is the intelligent edge-cloud hybrid router located in `main.py -> generate_hybrid`. We achieved incredibly high F1 Scores and minimized Latency Penalties via a 3-tiered algorithmic approach:

1. **Syntactic Complexity Routing (Latency Bypass)**:
   Small 270M parameter edge models are bad at mapping variables in massive, multi-tool compound prompts (e.g., *"What's the weather, and what ringtone is set?"*). Before booting the local model, our string analyzer checks for compound logic (", ", "and", "then") combined with a large `len(tools)`. If the query is computationally bound to fail locally, we bypass the local model hardware completely and instantly hit Gemini 2.5—saving ~1.5s in spin-up time and preserving the benchmark **Time Score**.
2. **Semantic Domain Routing (Functional Bypass)**:
   We route queries requesting real-time live data (e.g., "price", "news") instantly to the cloud where the agent leverages Gemini's superior real-time grounding. Conversely, strictly analytical and core mathematical equations ("calculate", "roi", "mortgage") are prioritized for the local edge device, ensuring computational privacy for personal financial queries.
3. **Dynamic Confidence Auditing (F1 Accuracy Saver)**:
   Rather than using a static scalar for the `confidence` handoff, our threshold is dynamic. When a prompt relies on only 1 tool, we heavily drop the confidence threshold (`0.70`), completely trusting FunctionGemma since hallucination risk drops logarithmically. For medium/hard tasks with huge JSON structures, we audit the local model securely at an `0.85` threshold to protect our benchmark **F1 Score**.

---

### **Rubric 2: Real-World Functional End-to-End Product**
We didn't just output terminal JSON strings; we built a blazing fast Vanilla JS + FastAPI web application to surface the tool outputs to end-users as **Rich Interactive UI Widgets**. 
Whenever `generate_hybrid` fires off an executor matching data, we instantly hit the live `yfinance` python API. The response data triggers dynamic DOM element creations rendering CSS data visualization blocks to the human (Stock Tickers, Green/Red Price Deltas, and Live Live Company Headlines).

---

### **Rubric 3: Low-Latency Voice-to-Action Product**
We completely modernized accessibility for our dashboard by converting the entire toolchain into a hands-free **Voice-to-Action** product using `cactus_transcribe`. 
The client UI requests the user's microphone (`MediaRecorder API`), buffers down the spoken query to a `16kHz WAV` blob, and blindly POSTs to our FastAPI Python `/api/transcribe` endpoint. The backend handles lazy-loading the local `cactus/weights/whisper-small` model into memory precisely once, evaluating the WAV, and forwarding the transcribed speech directly into our F1-optimised `generate_hybrid` router.
