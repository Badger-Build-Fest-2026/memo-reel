"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { GraphNode } from "@/lib/types";
import { CATEGORY_COLOR_KEY, CATEGORY_HEX } from "@/lib/types";

interface Props {
  node: GraphNode | null;
  onClose: () => void;
}

export default function NodeDetailPanel({ node, onClose }: Props) {
  const categoryHex = node
    ? CATEGORY_HEX[CATEGORY_COLOR_KEY[node.category as keyof typeof CATEGORY_COLOR_KEY] || "other"]
    : CATEGORY_HEX.other;

  return (
    <AnimatePresence>
      {node && (
        <motion.aside
          initial={{ x: 40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 40, opacity: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="absolute top-24 right-6 z-20 w-[360px] max-h-[calc(100vh-8rem)] overflow-y-auto glass-panel rounded-2xl p-6"
        >
          <div className="flex items-start justify-between mb-3">
            <span
              className="text-xs px-2 py-1 rounded-full"
              style={{ color: categoryHex, backgroundColor: `${categoryHex}1A` }}
            >
              {node.category}
            </span>
            <div className="flex items-center gap-3">
              {node.obsidian_url && (
                <a
                  href={node.obsidian_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open in Obsidian"
                  className="text-nebula hover:text-paper transition-colors"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M12 2L4 9L8 22L16 22L20 9L12 2Z"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      fill="currentColor"
                      fillOpacity="0.18"
                    />
                    <path
                      d="M12 2L8 9M12 2L16 9M4 9H20M8 9L8 22M16 9L16 22M8 9L12 14L16 9"
                      stroke="currentColor"
                      strokeWidth="1"
                    />
                  </svg>
                </a>
              )}
              <button
                onClick={onClose}
                className="text-dust hover:text-paper text-sm"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
          </div>

          <h2 className="font-display text-xl leading-snug mb-2">{node.label}</h2>

          {node.summary && (
            <p className="text-sm text-dust leading-relaxed mb-4">{node.summary}</p>
          )}

          {node.recipe && (
            <div className="mb-4 space-y-3">
              {(node.recipe.servings || node.recipe.cook_time) && (
                <div className="flex gap-4 text-xs text-dust">
                  {node.recipe.servings && <span>Serves {node.recipe.servings}</span>}
                  {node.recipe.cook_time && <span>{node.recipe.cook_time}</span>}
                </div>
              )}

              {node.recipe.ingredients.length > 0 && (
                <div>
                  <h3 className="text-xs uppercase tracking-wide text-dust mb-1.5">Ingredients</h3>
                  <ul className="space-y-1">
                    {node.recipe.ingredients.map((ing, i) => (
                      <li key={i} className="text-sm text-paper/90 flex items-start gap-2">
                        <span className="mt-1 w-1.5 h-1.5 rounded-full bg-starlight/70 shrink-0" />
                        {ing}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {node.recipe.steps.length > 0 && (
                <div>
                  <h3 className="text-xs uppercase tracking-wide text-dust mb-1.5">Steps</h3>
                  <ol className="space-y-1.5">
                    {node.recipe.steps.map((step, i) => (
                      <li key={i} className="text-sm text-paper/90 flex gap-2">
                        <span className="text-starlight/80 shrink-0">{i + 1}.</span>
                        {step}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}

          {node.product_list && node.product_list.length > 0 && (
            <div className="mb-4 space-y-3">
              <h3 className="text-xs uppercase tracking-wide text-dust mb-1.5">Products</h3>
              {node.product_list.map((p, i) => (
                <div key={i} className="border-l-2 pl-3" style={{ borderColor: `${categoryHex}55` }}>
                  <div className="text-sm text-paper font-medium">{p.name}</div>
                  <div className="text-xs text-dust leading-relaxed">{p.description}</div>
                  <div className="flex items-center gap-3 mt-1">
                    {p.price && <span className="text-xs text-starlight">{p.price}</span>}
                    {p.purchase_link && (
                      <a
                        href={p.purchase_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-nebula hover:underline"
                      >
                        View product
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
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
