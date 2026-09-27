"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { GraphNode } from "@/lib/types";
import { CATEGORY_COLOR_KEY, CATEGORY_HEX } from "@/lib/types";

interface Props {
  node: GraphNode | null;
  onClose: () => void;
}

export default function NodeDetailPanel({ node, onClose }: Props) {
  return (
    <AnimatePresence>
      {node && (
        <motion.aside
          initial={{ x: 40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 40, opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="absolute top-24 right-6 z-20 w-[340px] glass-panel rounded-2xl p-6"
        >
          <div className="flex items-start justify-between mb-3">
            <span
              className="text-xs px-2 py-1 rounded-full"
              style={{
                color: CATEGORY_HEX[CATEGORY_COLOR_KEY[node.category as keyof typeof CATEGORY_COLOR_KEY] || "other"],
                backgroundColor: `${CATEGORY_HEX[CATEGORY_COLOR_KEY[node.category as keyof typeof CATEGORY_COLOR_KEY] || "other"]}1A`,
              }}
            >
              {node.category}
            </span>
            <button
              onClick={onClose}
              className="text-dust hover:text-paper text-sm"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          <h2 className="font-display text-xl leading-snug mb-2">{node.label}</h2>

          {node.summary && (
            <p className="text-sm text-dust leading-relaxed mb-4">{node.summary}</p>
          )}

          {node.reel_url && (
            <a
              href={node.reel_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-sm text-starlight hover:underline"
            >
              Open original reel
            </a>
          )}
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
