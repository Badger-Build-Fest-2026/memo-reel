import type { ChatResponse, GraphResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export async function fetchGraph(userId: string): Promise<GraphResponse> {
  const res = await fetch(`${API_BASE}/graph?user_id=${encodeURIComponent(userId)}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to load graph (${res.status})`);
  return res.json();
}

export async function askChat(query: string, userId: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, user_id: userId }),
  });
  if (!res.ok) throw new Error(`Chat request failed (${res.status})`);
  return res.json();
}
