"use client";

import { CATEGORY_HEX } from "@/lib/types";

const CATEGORIES = [
  { label: "Food & Cooking", key: "food" },
  { label: "Technology & Education", key: "tech" },
  { label: "Shopping & Products", key: "shop" },
  { label: "Fitness & Health", key: "fitness" },
  { label: "Lifestyle & Travel", key: "lifestyle" },
  { label: "Entertainment", key: "entertainment" },
];

interface Props {
  activeCategory: string | null;
  onSelectCategory: (label: string | null) => void;
}

export default function TopBar({ activeCategory, onSelectCategory }: Props) {
  return (
    <header className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-8 py-6">
      <h1 className="font-display italic text-2xl tracking-tight text-paper">
        RecallGraph
      </h1>

      <div className="flex flex-wrap justify-end gap-2 max-w-xl">
        {CATEGORIES.map((c) => {
          const active = activeCategory === c.label;
          return (
            <button
              key={c.label}
              onClick={() => onSelectCategory(active ? null : c.label)}
              className="rounded-full px-3 py-1.5 text-xs transition-colors duration-200 border"
              style={{
                borderColor: active ? CATEGORY_HEX[c.key] : "rgba(242,239,230,0.15)",
                color: active ? CATEGORY_HEX[c.key] : "#8A90B3",
                backgroundColor: active ? `${CATEGORY_HEX[c.key]}1A` : "transparent",
              }}
            >
              {c.label}
            </button>
          );
        })}
      </div>
    </header>
  );
}
