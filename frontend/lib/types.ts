export type Category =
  | "Food & Cooking"
  | "Technology & Education"
  | "Shopping & Products"
  | "Fitness & Health"
  | "Lifestyle & Travel"
  | "Entertainment"
  | "Other";

export const CATEGORY_COLOR_KEY: Record<Category, string> = {
  "Food & Cooking": "food",
  "Technology & Education": "tech",
  "Shopping & Products": "shop",
  "Fitness & Health": "fitness",
  "Lifestyle & Travel": "lifestyle",
  Entertainment: "entertainment",
  Other: "other",
};

export const CATEGORY_HEX: Record<string, string> = {
  food: "#F0925C",
  tech: "#F0C15C",
  shop: "#8B7FFF",
  fitness: "#5CE0B8",
  lifestyle: "#F08CC2",
  entertainment: "#5CB8FF",
  other: "#9AA0C7",
};

// the central hub node representing the person themself - distinct
// from every category color so it reads as the one-of-a-kind anchor
export const USER_NODE_HEX = "#FDF3D9";

// one emoji per category (rendered as a billboard sprite on the node
// itself) plus the hub - purely visual, keyed the same way as
// CATEGORY_HEX so both stay in sync
export const CATEGORY_ICON: Record<string, string> = {
  food: "🍳",
  tech: "💻",
  shop: "🛍️",
  fitness: "💪",
  lifestyle: "✈️",
  entertainment: "🎬",
  other: "✨",
};

export const USER_NODE_ICON = "👤";

export interface RecipeInfo {
  ingredients: string[];
  steps: string[];
  servings?: string | null;
  cook_time?: string | null;
}

export interface ProductInfo {
  name: string;
  description: string;
  price?: string | null;
  purchase_link?: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  type: "reel" | "concept" | "category" | "user";
  category?: string | null;
  size: number;
  reel_url?: string | null;
  summary?: string | null;
  obsidian_url?: string | null;
  recipe?: RecipeInfo | null;
  product_list?: ProductInfo[] | null;
  // populated client-side by the force-graph library at runtime
  x?: number;
  y?: number;
  z?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// The real RAG agent (agent/langgraph_agent.py, run_reel_agent) returns
// a single markdown string with citations and [[wikilinks]] embedded
// inline - there is no separate structured sources list to render.
export interface ChatResponse {
  answer: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
