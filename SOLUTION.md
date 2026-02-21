# FinanceGemma: Hybrid Routing Architecture

The core of our Hackathon submission revolves around an intelligent edge-cloud hybrid router. This router dynamically balances the ultra-low latency, high-privacy capabilities of a local 270M parameter FunctionGemma model running on macOS against the profound reasoning capabilities of Gemini 2.5 Flash in the cloud.

Below are the key architectural decisions and routing strategies we implemented inside the `generate_hybrid` algorithm to achieve strong F1 scores while prioritizing edge constraints.

## 1. Pre-emptive Hard-Task Cloud Routing (Latency Optimization)

Small, 270M parameter edge models excel at singular, highly specific classification or mapping tasks. However, they drastically drop in performance (F1 Score) when presented with a large toolset alongside a compound query (e.g., *"What's the weather like in SF, and can you set an alarm for an hour?"*). 

**Strategy:** 
Before the local model is even invoked, the algorithm performs a heuristic-based string analysis on the user's prompt. 
- It checks if the query contains coordinating conjunctions indicating a multi-step operation (e.g., `" and "`, `"also"`, `"then"`, `", "`).
- It checks the complexity of the available toolset (e.g., `len(tools) >= 3`).

If both conditions are met, the request is routed **directly to Gemini 2.5 Flash**. 
**Reasoning:** If we attempt this compound task on the edge device, FunctionGemma is likely to perform poorly (low confidence). This would result in a fallback to the cloud anyway. By routing directly, we save the ~1,500ms of local inference spin-up time, dramatically improving the Time Score in our benchmarks while preserving the F1 Accuracy.

## 2. Dynamic Confidence Thresholding (Accuracy Optimization)

If the query is safe for local execution, we send it to `FunctionGemma`. `FunctionGemma` returns a set of tool parameters alongside a `confidence` metric. In a naive implementation, a static threshold (like `0.99`) decides if the response is safe. We improved this.

**Strategy:**
The confidence threshold is determined dynamically at runtime based on the contextual difficulty of the request.
- **Easy Task (1 Tool):** If only one tool is provided to the agent, the probability of catastrophic hallucination mapping is extremely low. Thus, we comfortably lower the threshold to `0.70`.
- **Medium/Hard Task (Multiple Tools):** If multiple tools are provided, the risk of incorrect parameter mapping increases. We strictly hold the local model accountable with a default threshold of `0.85`.

**Reasoning:** 
If `FunctionGemma` predicts with high confidence (e.g., `0.90`) on an easy task, the hybrid router instantly returns the local result. If the model exhibits low confidence (e.g., `0.45` when evaluating exchange rates), the router instantly intercepts the result and delegates the task to the cloud layer as a fallback. This maximizes our **On-Device Ratio** for simple commands without bleeding accuracy.

## 3. FunctionGemma Setup & Model Integrity
One of our early challenges was configuring the local infrastructure. The official `google/functiongemma-270m-it` on HuggingFace is gated. However, utilizing the bespoke Cactus infrastructure, we downloaded the pre-converted int8 quantized weights from the Cactus servers directly. 
The Web Application (`app.py`) natively boots this local 270M model directly into the active CPU RAM of the Mac via the `cactus_init` Python FFI bindings, executing true local generation seamlessly.
