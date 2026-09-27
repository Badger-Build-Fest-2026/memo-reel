"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { askChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

interface Props {
  userId: string;
}

// The agent writes Obsidian-style [[Concept]] wikilinks, which aren't
// real markdown syntax - react-markdown would just show the literal
// brackets. Turn them into a styled span (colored like the graph's
// concept nodes) before handing the string to the markdown renderer.
function preprocessWikilinks(text: string): string {
  return text.replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink">$1</span>');
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
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
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
    <div className="absolute bottom-6 left-6 z-20 w-[440px] max-w-[calc(100vw-3rem)]">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 460 }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="glass-panel rounded-2xl mb-3 overflow-hidden flex flex-col"
          >
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
              {messages.length === 0 && (
                <p className="text-dust text-sm">
                  Ask about anything you've saved — "prep me for a data science interview"
                  or "what meal prep recipes did I save".
                </p>
              )}
              {messages.map((m, i) => (
                <div key={i} className="text-sm leading-relaxed">
                  <span className="text-xs uppercase tracking-wide text-dust block mb-1">
                    {m.role === "user" ? "You" : "MemoReel"}
                  </span>
                  {m.role === "user" ? (
                    <span className="text-paper">{m.content}</span>
                  ) : (
                    <div className="chat-markdown text-paper/90">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeRaw]}
                      >
                        {preprocessWikilinks(m.content)}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              ))}
              {loading && <p className="text-dust text-sm italic">Thinking…</p>}
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
