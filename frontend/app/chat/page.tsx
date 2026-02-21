"use client";

import Link from "next/link";
import { useState, useRef, useEffect } from "react";

type TextBlock = { type: "text"; content?: string; data?: string };
type StockBlock = { type: "stock_widget"; data: { ticker: string; name: string; price: number } };
type NewsBlock = { type: "news_widget"; data: { ticker: string; headlines: { title: string; link: string }[] } };
type Block = TextBlock | StockBlock | NewsBlock;
type ResponseContent = string | Block[];

type Message = { role: "user" | "assistant"; content: ResponseContent };
type Metrics = { source: string; confidence: number; latency_ms: number } | null;

function formatText(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\\n/g, "<br/>");
}

function MessageBubble({ role, content }: { role: "user" | "assistant"; content: ResponseContent }) {
  if (typeof content === "string") {
    return (
      <div
        className={`rounded-2xl px-4 py-3 max-w-[85%] ${
          role === "user" ? "bg-blue-600 ml-auto" : "bg-zinc-800"
        }`}
        dangerouslySetInnerHTML={{ __html: formatText(content) }}
      />
    );
  }
  return (
    <div className="rounded-2xl bg-zinc-800 px-4 py-3 max-w-[85%] space-y-2">
      {content.map((block, i) => {
        if (block.type === "text") {
          const t = block.content ?? block.data ?? "";
          return (
            <div key={i} dangerouslySetInnerHTML={{ __html: formatText(t) }} />
          );
        }
        if (block.type === "stock_widget") {
          return (
            <div key={i} className="rounded-lg bg-zinc-900 p-3">
              <div className="text-zinc-400 text-sm">{block.data.ticker} – {block.data.name}</div>
              <div className="text-xl font-semibold text-green-400">${block.data.price.toFixed(2)}</div>
            </div>
          );
        }
        if (block.type === "news_widget") {
          return (
            <div key={i} className="rounded-lg bg-zinc-900 p-3">
              <div className="text-zinc-400 text-sm mb-2">Latest news for {block.data.ticker}</div>
              <ul className="list-disc list-inside space-y-1 text-sm">
                {block.data.headlines.map((h, j) => (
                  <li key={j}>
                    <a href={h.link} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
                      {h.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hi! I’m your finance assistant. Ask for stock prices, company news, ROI, exchange rates, or mortgage calculations.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [forceLocal, setForceLocal] = useState(false);
  const [metrics, setMetrics] = useState<Metrics>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
          {
            role: "assistant",
            content: "Conversation cleared. How can I help you?",
          },
        ]);
        setMetrics(data.metrics ?? { source: "—", confidence: 0, latency_ms: 0 });
      } else {
        setMessages((m) => [...m, { role: "assistant", content: data.response }]);
        setMetrics(data.metrics ?? null);
      }
    } catch (err) {
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
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Could not clear." }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <Link href="/" className="text-zinc-400 hover:text-white text-sm">
          ← Home
        </Link>
        <h1 className="bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-lg font-semibold text-transparent">
          Finance Gemma
        </h1>
        <button
          type="button"
          onClick={handleClear}
          disabled={loading}
          className="text-zinc-400 hover:text-white text-sm disabled:opacity-50"
        >
          Clear
        </button>
      </header>

      <div className="flex flex-1 flex-col md:flex-row min-h-0">
        <aside className="md:w-56 border-b md:border-b-0 md:border-r border-zinc-800 p-4 space-y-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={forceLocal}
              onChange={(e) => setForceLocal(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-zinc-400">Force local AI</span>
          </label>
          {metrics && (
            <div className="text-xs text-zinc-500 space-y-1">
              <div>Source: {metrics.source}</div>
              <div>Confidence: {(metrics.confidence * 100).toFixed(1)}%</div>
              <div>Latency: {metrics.latency_ms.toFixed(0)} ms</div>
            </div>
          )}
        </aside>

        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
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
                <div className="rounded-2xl bg-zinc-800 px-4 py-3 text-zinc-500 text-sm">
                  Thinking…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={handleSubmit} className="p-4 border-t border-zinc-800 flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. What is the stock price of AAPL?"
              className="flex-1 rounded-lg bg-zinc-800 px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-lg bg-blue-600 px-5 py-3 font-medium text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
