"use client";

import { useState, useRef, useEffect } from "react";

type TextBlock = { type: "text"; content?: string; data?: string };
type Block = TextBlock;
type ResponseContent = string | Block[];

type Message = { role: "user" | "assistant"; content: ResponseContent };
type Metrics = { source: string; confidence: number; latency_ms: number } | null;
type IndexStatus = { library_root: string | null; last_run: number | null; files_indexed: number; indexed_files?: string[]; errors: string[] };
type SuggestedRoot = { label: string; path: string };
type RequestFiles = { requestIndex: number; files: string[] };

function formatText(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\\n/g, "<br/>");
}

function MessageBubble({ role, content }: { role: "user" | "assistant"; content: ResponseContent }) {
  if (typeof content === "string") {
    return (
      <div
        className={`rounded-2xl px-4 py-3 max-w-[85%] text-sm text-neutral-200 transition-all duration-150 ${
          role === "user" ? "bg-blue-600/90 ml-auto text-white" : "bg-neutral-900 border border-neutral-800 shadow-sm"
        }`}
        dangerouslySetInnerHTML={{ __html: formatText(content) }}
      />
    );
  }
  return (
    <div className="rounded-2xl bg-neutral-900 border border-neutral-800 px-4 py-3 max-w-[85%] space-y-2 text-sm text-neutral-200 shadow-sm transition-all duration-150">
      {content.map((block, i) => {
        if (block.type === "text") {
          const t = (block as TextBlock).content ?? (block as TextBlock).data ?? "";
          return (
            <div key={i} dangerouslySetInnerHTML={{ __html: formatText(t) }} />
          );
        }
        return null;
      })}
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hi! I’m Deep-Focus. Set your library root and index to ask about your files (e.g. syllabus, quiz timeline, lecture notes).",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [forceLocal, setForceLocal] = useState(false);
  const [metrics, setMetrics] = useState<Metrics>(null);
  const [libraryRoot, setLibraryRoot] = useState("");
  const [suggestedRoots, setSuggestedRoots] = useState<SuggestedRoot[]>([]);
  const [indexStatus, setIndexStatus] = useState<IndexStatus | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [pathPickerValue, setPathPickerValue] = useState("");
  const [validateResult, setValidateResult] = useState<{ ok: boolean; error?: string; path?: string; file_count?: number } | null>(null);
  const [validating, setValidating] = useState(false);
  const [filesTouchedByRequest, setFilesTouchedByRequest] = useState<RequestFiles[]>([]);
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    fetch("/api/library/root")
      .then((r) => r.json())
      .then((d) => {
        const root = d.root ?? "";
        setLibraryRoot(root);
        setPathPickerValue(root);
      })
      .catch(() => {});
    fetch("/api/library/status")
      .then((r) => r.json())
      .then(setIndexStatus)
      .catch(() => {});
    fetch("/api/library/suggested-roots")
      .then((r) => r.json())
      .then((d) => setSuggestedRoots(d.roots ?? []))
      .catch(() => {});
  }, []);

  async function handleSetRootByPath(path: string) {
    setValidateResult(null);
    try {
      const putRes = await fetch("/api/library/root", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ root: path }),
      });
      const putData = await putRes.json().catch(() => ({}));
      const root = putData.root ?? "";
      setLibraryRoot(root);
      setPathPickerValue(root);
      if (!putRes.ok || putData.ok === false) {
        setValidateResult({ ok: false, error: putData.error ?? "Set path failed" });
        return;
      }
      setValidateResult({ ok: true, path: root, file_count: undefined });
      // Trigger index so backend agent uses this path immediately
      const indexRes = await fetch("/api/library/index", { method: "POST" });
      const indexData = await indexRes.json();
      if (indexData.ok && indexData.status) setIndexStatus(indexData.status);
      const statusRes = await fetch("/api/library/status");
      setIndexStatus(await statusRes.json());
    } catch (e) {
      setValidateResult({ ok: false, error: e instanceof Error ? e.message : "Request failed" });
    }
  }

  async function handleValidate() {
    const path = pathPickerValue.trim() || libraryRoot;
    if (!path) {
      setValidateResult({ ok: false, error: "Enter or set a path first" });
      return;
    }
    setValidating(true);
    setValidateResult(null);
    try {
      const res = await fetch("/api/library/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      const data = await res.json();
      setValidateResult(data.ok ? { ok: true, file_count: data.file_count, path: data.path } : { ok: false, error: data.error ?? "Invalid", path: data.path });
    } catch {
      setValidateResult({ ok: false, error: "Request failed" });
    } finally {
      setValidating(false);
    }
  }

  async function handleIndex() {
    setIndexing(true);
    try {
      const res = await fetch("/api/library/index", { method: "POST" });
      const data = await res.json();
      if (data.ok && data.status) setIndexStatus(data.status);
      else if (data.error) setIndexStatus((s) => ({ ...(s || {}), errors: [data.error] } as IndexStatus));
      const statusRes = await fetch("/api/library/status");
      setIndexStatus(await statusRes.json());
    } finally {
      setIndexing(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, force_local: forceLocal }),
      });
      const data = await res.json();

      if (text.toLowerCase() === "clear") {
        setMessages([
          { role: "assistant", content: "Conversation cleared. How can I help you?" },
        ]);
        setMetrics(data.metrics ?? { source: "—", confidence: 0, latency_ms: 0 });
        setFilesTouchedByRequest([]);
      } else if (!res.ok) {
        setMessages((m) => [...m, { role: "assistant", content: data.response ?? data.error ?? "Request failed." }]);
        setMetrics(data.metrics ?? null);
      } else {
        setMessages((m) => [...m, { role: "assistant", content: data.response }]);
        setMetrics(data.metrics ?? null);
        const touched = (data.files_touched as string[] | undefined) ?? [];
        setFilesTouchedByRequest((prev) => [...prev, { requestIndex: prev.length + 1, files: touched }]);
      }
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleClear() {
    setLoading(true);
    try {
      await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "clear" }),
      });
      setMessages([
        { role: "assistant", content: "Conversation cleared. How can I help you?" },
      ]);
      setMetrics(null);
      setFilesTouchedByRequest([]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Could not clear." }]);
    } finally {
      setLoading(false);
    }
  }

  async function startVoiceInput() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (chunks.length === 0) return;
        const blob = new Blob(chunks, { type: "audio/webm" });
        const form = new FormData();
        form.append("audio", blob, "recording.webm");
        try {
          const res = await fetch("/api/transcribe", {
            method: "POST",
            body: form,
          });
          const data = await res.json();
          if (data.text) setInput((prev) => (prev ? `${prev} ${data.text}` : data.text));
        } catch {
          setInput((prev) => (prev ? `${prev} [Transcription failed]` : "[Transcription failed]"));
        }
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch {
      setRecording(false);
    }
  }

  function stopVoiceInput() {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
    }
    setRecording(false);
  }

  function toggleVoice() {
    if (recording) stopVoiceInput();
    else startVoiceInput();
  }

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-neutral-950 text-neutral-200">
      <header className="shrink-0 flex items-center justify-between border-b border-neutral-800 px-6 py-4">
        <h1 className="text-xl font-semibold text-white">
          Deep-Focus
        </h1>
        <button
          type="button"
          onClick={handleClear}
          disabled={loading}
          className="text-sm font-medium text-neutral-400 hover:text-white transition-all duration-150 disabled:opacity-50 active:scale-[0.98]"
        >
          Clear chat
        </button>
      </header>

      <div className="flex flex-1 min-h-0 overflow-hidden max-w-7xl w-full mx-auto">
        <aside className="w-72 shrink-0 border-r border-neutral-800 bg-neutral-950 p-6 flex flex-col gap-6 overflow-y-auto min-h-0">
          <section className="space-y-4">
            <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-400">Library location</h2>
            <div>
              <label className="text-xs font-medium uppercase tracking-wide text-neutral-500 block mb-2">Path picker (path sent to backend)</label>
                <div className="flex flex-col gap-2 flex-1 min-w-0">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={pathPickerValue}
                      onChange={(e) => { setPathPickerValue(e.target.value); setValidateResult(null); }}
                      placeholder="/path/to/folder"
                      className="flex-1 min-w-0 rounded-lg bg-neutral-900 border border-neutral-800 px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-150"
                    />
                    <button
                      type="button"
                      onClick={() => pathPickerValue.trim() && handleSetRootByPath(pathPickerValue.trim())}
                      disabled={indexing || !pathPickerValue.trim()}
                      className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 shrink-0 transition-all duration-150 ease-out active:scale-[0.98]"
                    >
                      Set
                    </button>
                    <button
                      type="button"
                      onClick={handleValidate}
                      disabled={validating}
                      className="rounded-lg bg-neutral-800 px-3 py-2 text-sm font-medium text-neutral-200 hover:bg-neutral-700 disabled:opacity-50 shrink-0 transition-all duration-150 ease-out active:scale-[0.98]"
                    >
                      {validating ? "…" : "Validate"}
                    </button>
                  </div>
                  <label className="flex items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-700 p-2 text-xs text-neutral-500 hover:border-neutral-500 hover:text-neutral-400 cursor-pointer transition-all">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" /></svg>
                    <span>Choose folder from machine...</span>
                    <input
                      type="file"
                      // @ts-ignore
                      webkitdirectory=""
                      directory=""
                      className="hidden"
                      onChange={async (e) => {
                        const files = e.target.files;
                        if (!files || files.length === 0) return;
                        
                        setIndexing(true);
                        const formData = new FormData();
                        for (let i = 0; i < files.length; i++) {
                          formData.append("files", files[i]);
                        }
                        
                        try {
                          const res = await fetch("/api/library/upload", {
                            method: "POST",
                            body: formData
                          });
                          const data = await res.json();
                          if (data.ok) {
                            setLibraryRoot(data.root);
                            setPathPickerValue(data.root);
                            if (data.status) setIndexStatus(data.status);
                          }
                        } catch (err) {
                          console.error("Upload failed", err);
                        } finally {
                          setIndexing(false);
                        }
                      }}
                    />
                  </label>
                </div>
              {validateResult && (
                <div className={`mt-2 text-xs ${validateResult.ok ? "text-green-500" : "text-amber-500"}`}>
                  {validateResult.ok ? (
                    <p>Valid directory{validateResult.file_count != null ? ` (${validateResult.file_count} files)` : ""}{validateResult.path ? `: ${validateResult.path}` : ""}</p>
                  ) : (
                    <>
                      <p>{validateResult.error}</p>
                      {validateResult.path && <p className="truncate mt-0.5 text-neutral-500" title={validateResult.path}>Tried: {validateResult.path}</p>}
                      {validateResult.error?.includes("Path does not exist") && (
                        <p className="mt-1 text-neutral-500">Tip: Run the backend on this computer (not in Docker) so it can read your folders: <code className="text-neutral-400">uvicorn backend.main:app --port 8000</code></p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
            {suggestedRoots.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">Or pick a location</p>
                <div className="flex flex-col gap-1">
                  {suggestedRoots.map((r) => (
                    <button
                      key={r.path}
                      type="button"
                      onClick={() => handleSetRootByPath(r.path)}
                      disabled={indexing}
                      className="rounded-lg bg-neutral-800 px-3 py-2 text-left text-sm text-neutral-200 hover:bg-neutral-700 disabled:opacity-50 transition-all duration-150 ease-out active:scale-[0.98]"
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {libraryRoot && (
              <p className="text-xs text-neutral-500 truncate" title={libraryRoot}>
                Current: {libraryRoot}
              </p>
            )}
            <button
              type="button"
              onClick={handleIndex}
              disabled={indexing || !libraryRoot}
              className="w-full rounded-lg bg-neutral-800 px-3 py-2 text-sm font-medium text-neutral-200 hover:bg-neutral-700 disabled:opacity-50 transition-all duration-150 ease-out active:scale-[0.98]"
            >
              {indexing ? "Indexing…" : "Re-index"}
            </button>
            {indexStatus && (
              <div className="space-y-3">
                <div className="space-y-1 text-xs text-neutral-500">
                  {indexStatus.files_indexed != null && (
                    <div className="flex justify-between">
                      <span>Files indexed:</span>
                      <span className="font-semibold text-neutral-400">{indexStatus.files_indexed}</span>
                    </div>
                  )}
                  {indexStatus.last_run != null && (
                    <div className="flex justify-between">
                      <span>Last run:</span>
                      <span className="font-semibold text-neutral-400">{new Date(indexStatus.last_run * 1000).toLocaleString()}</span>
                    </div>
                  )}
                  {indexStatus.errors?.length > 0 && (
                    <div className="text-amber-500">{indexStatus.errors.length} error(s)</div>
                  )}
                </div>

                {indexStatus.indexed_files && indexStatus.indexed_files.length > 0 && (
                  <div className="space-y-2 border-t border-neutral-800 pt-3">
                    <h2 className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">Library Content</h2>
                    <ul className="max-h-48 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                      {indexStatus.indexed_files.map((file, i) => (
                        <li key={i} className="group flex items-center gap-2 rounded-md px-2 py-1.5 text-[11px] text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-200 transition-colors">
                          <svg className="w-3 h-3 text-neutral-600 group-hover:text-neutral-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span className="truncate" title={file}>{file.split('/').pop()}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </section>
          <section>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={forceLocal}
                onChange={(e) => setForceLocal(e.target.checked)}
                className="rounded border-neutral-600 bg-neutral-900 text-blue-500 focus:ring-2 focus:ring-blue-500 transition-all duration-150"
              />
              <span className="text-sm text-neutral-400">Force local AI</span>
            </label>
          </section>
          {metrics && (
            <section className="space-y-3">
              <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-400">Metrics</h2>
              <div className="grid gap-2 rounded-xl border border-neutral-800 bg-neutral-900/80 p-3 shadow-sm">
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-neutral-500">Source</div>
                  <div className="text-sm font-semibold text-neutral-200">{metrics.source}</div>
                </div>
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-neutral-500">Confidence</div>
                  <div className="text-sm font-semibold text-neutral-200">{(metrics.confidence * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-neutral-500">Latency</div>
                  <div className="text-sm font-semibold text-neutral-200">{metrics.latency_ms.toFixed(0)} ms</div>
                </div>
              </div>
            </section>
          )}
          {filesTouchedByRequest.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-400">Files touched per request</h2>
              <ul className="space-y-2 text-sm">
                {filesTouchedByRequest.map(({ requestIndex, files }, i) => (
                  <li key={i} className="rounded-xl border border-neutral-800 bg-neutral-900/80 p-3 shadow-sm transition-all duration-150 hover:-translate-y-[1px] hover:shadow-md">
                    <div className="text-xs font-medium uppercase tracking-wide text-neutral-500 mb-1">Request {requestIndex}</div>
                    {files.length === 0 ? (
                      <div className="text-neutral-500 italic text-sm">—</div>
                    ) : (
                      <ul className="list-disc list-inside text-neutral-400 space-y-0.5 truncate text-sm" title={files.join("\n")}>
                        {files.map((f, j) => (
                          <li key={j} className="truncate" title={f}>{f}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>

        <main className="flex-1 flex flex-col min-h-0 border-l border-neutral-800 overflow-hidden">
          <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-6">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <MessageBubble role={msg.role} content={msg.content} />
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-neutral-900 border border-neutral-800 px-4 py-3 text-sm text-neutral-500 shadow-sm">
                  Thinking…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
          <form onSubmit={handleSubmit} className="shrink-0 p-6 border-t border-neutral-800 flex gap-3">
            <button
              type="button"
              onClick={toggleVoice}
              title={recording ? "Stop recording" : "Voice input"}
              className={`rounded-lg px-4 py-3 shrink-0 transition-all duration-150 ease-out active:scale-[0.98] ${recording ? "bg-red-600 hover:bg-red-500" : "bg-neutral-800 hover:bg-neutral-700"} text-white disabled:opacity-50`}
              disabled={loading}
            >
              <span className="sr-only">{recording ? "Stop" : "Mic"}</span>
              {recording ? (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
              ) : (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5-3c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>
              )}
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. Summarize the syllabus · What's the quiz timeline? · When is the next assignment due?"
              className="flex-1 rounded-lg bg-neutral-900 border border-neutral-800 px-4 py-3 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-150"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-lg bg-blue-600 px-5 py-3 font-medium text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 ease-out active:scale-[0.98]"
            >
              Send
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}
