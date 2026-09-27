"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { askChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

interface Props {
  userId: string;
}

export default function ChatDock({ userId }: Props) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const threadEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const query = input.trim();
    if (!query || loading) return;

    setOpen(true);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: query }]);
    setLoading(true);

    try {
      const res = await askChat(query, userId);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, sources: res.sources },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong reaching your knowledge base. Try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="absolute bottom-6 left-6 z-20 w-[400px] max-w-[calc(100vw-3rem)]">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 420 }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="glass-panel rounded-2xl mb-3 overflow-hidden flex flex-col"
          >
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
              {messages.length === 0 && (
                <p className="text-dust text-sm">
                  Ask about anything you've saved — "what was that sandwich recipe" or
                  "which reels mentioned Redis".
                </p>
              )}
              {messages.map((m, i) => (
                <div key={i}>
                  <div
                    className={`text-sm leading-relaxed ${
                      m.role === "user" ? "text-paper" : "text-paper/90"
                    }`}
                  >
                    <span className="text-xs uppercase tracking-wide text-dust block mb-1">
                      {m.role === "user" ? "You" : "RecallGraph"}
                    </span>
                    {m.content}
                  </div>
                  {m.sources && m.sources.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {m.sources.map((s) => (
                        <span
                          key={s.id}
                          className="text-[11px] px-2 py-1 rounded-full border border-nebula/40 text-nebula"
                        >
                          {s.title}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {loading && <p className="text-dust text-sm italic">Searching your reels…</p>}
              <div ref={threadEndRef} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <form
        onSubmit={handleSubmit}
        className="glass-panel rounded-full flex items-center px-4 py-3 gap-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onFocus={() => messages.length > 0 && setOpen(true)}
          placeholder="Ask your knowledge base..."
          className="flex-1 bg-transparent outline-none text-sm text-paper placeholder:text-dust"
        />
        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="text-dust hover:text-paper text-xs"
            aria-label={open ? "Collapse chat" : "Expand chat"}
          >
            {open ? "▾" : "▴"}
          </button>
        )}
      </form>
    </div>
  );
}
