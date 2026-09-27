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

export interface GraphNode {
  id: string;
  label: string;
  type: "reel" | "concept" | "category" | "user";
  category?: string | null;
  size: number;
  reel_url?: string | null;
  summary?: string | null;
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
