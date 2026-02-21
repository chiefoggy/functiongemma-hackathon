# Deep-Focus: Privacy-First File Assistant

**Deep-Focus** is a local-first assistant that treats a **user-specified root folder** as your **library and learning hub**—the one place for all course materials, syllabi, timelines, and notes. It indexes files under that root, retrieves and analyzes content from your queries, and decides whether to answer on-device or offload to the cloud. Sensitive operations stay on the machine; only when local capability is insufficient does the request go to Gemini.

---

## Core Function

1. **User-specified root = your library and learning hub**  
   The user picks one root folder (e.g. `~/StudyVault`, `./courses`, `~/Documents/learning`). This root acts as a **library and learning hub**—syllabi, lecture notes, PDFs, code, slides, spreadsheets, and any file that might contain schedules or timelines (e.g. quiz dates, assignment due dates). The system indexes everything under that root, extracts text from supported formats, and answers questions from that corpus only. One root, one hub.

2. **Content retrieval and simple analysis**  
   From a user request (see example questions below), the system:
   - Retrieves relevant chunks from the index
   - Performs simple analysis (summaries, key points, code explanations) on-device when possible

3. **Hybrid routing: when to offload to the cloud**  
   - **Local**: Lookups, short summaries, single-file or low-complexity questions. Uses on-device model + local RAG; no data leaves the machine.
   - **Cloud**: Complex reasoning, multi-document synthesis, or when local confidence is below a threshold. Request (optionally scrubbed) is sent to Gemini; response is shown with a cloud badge.

4. **Supported formats**  
   - **Documents**: PDF, DOC/DOCX  
   - **Code**: common extensions (e.g. `.py`, `.js`, `.ts`, `.go`, `.md`)  
   - **Data / sheets**: CSV, XLSX (e.g. first N rows → markdown table)  
   - **Other**: plain text, Markdown, and other standard formats as needed  

   Parsers extract searchable text (and optionally structure) so retrieval and analysis work across these types.

---

## Example questions (library / learning hub)

Users can ask natural-language questions over their indexed materials. The system retrieves from PDFs, docs, spreadsheets, or markdown (where timelines and schedules often live) and returns summaries or direct answers. Examples:

- **“Summarize the syllabus for this course.”** — Pulls from syllabus PDFs or docs under the root and returns a concise overview (topics, grading, deadlines).
- **“What’s the quiz timeline?”** — Assumes some file under the root contains a timeline or schedule (e.g. a CSV, a table in a PDF, or a markdown list); retrieves and surfaces quiz dates or a timeline.
- **“When are the assignments due?”** — Same idea: find schedule/timeline content in the hub and return due dates.
- **“Summarize the main functions in `src/utils.py`.”** / **“What did the Q3 report say about revenue?”** — Code or document lookups and short analysis from the indexed corpus.

---

## Technical Selling Points (including privacy)

- **Sensitive content stays on-device**  
  Indexing, retrieval, and simple analysis run locally. Only when the system decides to offload (e.g. low confidence, complex query) does content go to the cloud—and a **privacy scrubber** can redact names, IDs, or custom PII before the request is sent.

- **Auditable local vs cloud**  
  Every response is tagged with **source** (on-device / cloud), **confidence**, and **latency**. Users and admins can see which queries were answered locally and which used the cloud, for compliance and audits.

- **Automatic routing**  
  No user toggle: the system uses query semantics, complexity, and local confidence to choose local vs cloud, so simple file lookups are fast and private while hard questions still get strong answers.

---

## Feature Summary (concrete)

| Feature | What it does | Sell |
|--------|----------------|------|
| **Library & learning hub (user root)** | User sets one root folder as their library/hub: syllabi, notes, PDFs, code, timelines (e.g. quiz/assignment schedules). Index supports PDF, DOC, code, CSV, XLSX, etc. | “One hub, all your materials. Ask e.g. ‘Summarize the syllabus’ or ‘What’s the quiz timeline?’” |
| **Retrieve + simple analysis** | Return relevant snippets and short summaries or explanations from indexed content. | “Find and understand without opening every file.” |
| **Local-first answers** | Single-file or simple questions answered entirely on-device (RAG + local model). | “No upload for normal lookups; privacy by default.” |
| **Cloud offload when needed** | Complex or low-confidence queries go to Gemini (with optional scrub). | “Hard questions get cloud quality; you see when it’s used.” |
| **Source + metrics** | Show on-device vs cloud and latency/confidence per answer. | “Transparent for users and for compliance.” |

---

## One-line pitches

- **Privacy / compliance**: “We index and search your files on your machine. Only when we can’t answer confidently do we send a request to the cloud—and we can scrub it first.”
- **Product**: “Set your root folder as your library and learning hub. Ask things like ‘Summarize the syllabus for this course’ or ‘What’s the quiz timeline?’—we retrieve from your files (PDFs, docs, spreadsheets, etc.), do simple analysis locally, and only offload to the cloud when necessary.”
- **Enterprise**: “Every answer is tagged local or cloud. You can enforce policies and show auditors exactly when data left the device.”
