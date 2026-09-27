"use client";

import { useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import TopBar from "@/components/TopBar";
import ChatDock from "@/components/ChatDock";
import NodeDetailPanel from "@/components/NodeDetailPanel";
import { fetchGraph } from "@/lib/api";
import type { GraphNode, GraphResponse } from "@/lib/types";

// the 3D graph touches WebGL/DOM directly - never render it on the server
const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), { ssr: false });

// swap for real auth/user context once that exists - a query param is
// enough to demo multiple users' graphs during the hackathon.
// Starts as null (not "demo") so the fetch effect below waits for the
// real value instead of firing once for "demo" and once for the real
// id - two in-flight fetches with no cancellation means whichever
// resolves last wins, which could silently overwrite real data with
// an empty "demo" result.
function useUserId(): string | null {
  const [userId, setUserId] = useState<string | null>(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setUserId(params.get("user") || "demo");
  }, []);
  return userId;
}

export default function Home() {
  const userId = useUserId();
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    if (!userId) return; // wait for the real value from the URL, see useUserId above
    fetchGraph(userId)
      .then(setGraphData)
      .catch(() => setError("Couldn't reach the knowledge graph. Is the backend running?"));
  }, [userId]);

  const filteredData = useMemo<GraphResponse | null>(() => {
    if (!graphData) return null;
    if (!activeCategory) return graphData;

    const keepNodeIds = new Set(
      graphData.nodes
        .filter((n) => n.type !== "category" && n.category === activeCategory)
        .map((n) => n.id)
    );
    const categoryNodeId = graphData.nodes.find(
      (n) => n.type === "category" && n.label === activeCategory
    )?.id;
    if (categoryNodeId) keepNodeIds.add(categoryNodeId);

    return {
      nodes: graphData.nodes.filter((n) => keepNodeIds.has(n.id)),
      edges: graphData.edges.filter((e) => keepNodeIds.has(e.source) && keepNodeIds.has(e.target)),
    };
  }, [graphData, activeCategory]);

  // one central hub node representing the person, spoked out to each
  // category present - gives the graph a deliberate center instead of
  // categories drifting apart as disconnected clusters
  const displayData = useMemo<GraphResponse | null>(() => {
    if (!filteredData || filteredData.nodes.length === 0) return filteredData;

    const categoryNodes = filteredData.nodes.filter((n) => n.type === "category");
    const hubNode: GraphNode = { id: "user:hub", label: "You", type: "user", size: 4 };
    const hubEdges = categoryNodes.map((c) => ({ source: hubNode.id, target: c.id }));

    return {
      nodes: [hubNode, ...filteredData.nodes],
      edges: [...hubEdges, ...filteredData.edges],
    };
  }, [filteredData]);

  return (
    <main className="relative w-screen h-screen overflow-hidden">
      <TopBar activeCategory={activeCategory} onSelectCategory={setActiveCategory} />

      {error && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-dust text-sm max-w-xs text-center">{error}</p>
        </div>
      )}

      {!error && filteredData && filteredData.nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-dust text-sm max-w-xs text-center">
            Save a reel to start building your knowledge graph.
          </p>
        </div>
      )}

      {!error && displayData && displayData.nodes.length > 0 && (
        <KnowledgeGraph data={displayData} onSelectReel={setSelectedNode} />
      )}

      <NodeDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} />

      {userId && <ChatDock userId={userId} />}
    </main>
  );
}
