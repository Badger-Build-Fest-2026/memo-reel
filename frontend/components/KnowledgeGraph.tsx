"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";
import { CATEGORY_COLOR_KEY, CATEGORY_HEX, CATEGORY_ICON, USER_NODE_HEX, USER_NODE_ICON } from "@/lib/types";

interface Props {
  data: GraphResponse;
  onSelectReel: (node: GraphNode) => void;
}

type Vec3 = { x: number; y: number; z: number };

const HUB_RADIUS = 90;      // hub -> category ring
const REEL_RING_RADIUS = 32; // category -> its own reels' sub-ring

function colorForNode(node: GraphNode): string {
  if (node.type === "user") return USER_NODE_HEX;
  const categoryLabel = node.type === "category" ? node.label : node.category;
  const key = CATEGORY_COLOR_KEY[categoryLabel as keyof typeof CATEGORY_COLOR_KEY];
  const hex = (key && CATEGORY_HEX[key]) || CATEGORY_HEX.other;
  if (node.type === "concept") return hex + "99";
  return hex;
}

// only the hub and category nodes get an icon - reels/concepts stay
// plain so the icon reads as "this is a top-level anchor," not noise
// repeated on every small node
function iconForNode(node: GraphNode): string | null {
  if (node.type === "user") return USER_NODE_ICON;
  if (node.type === "category") {
    const key = CATEGORY_COLOR_KEY[node.label as keyof typeof CATEGORY_COLOR_KEY];
    return (key && CATEGORY_ICON[key]) || CATEGORY_ICON.other;
  }
  return null;
}

function buildCategoryAnchors(categoryLabels: string[]): Map<string, Vec3> {
  const anchors = new Map<string, Vec3>();
  const n = categoryLabels.length;
  categoryLabels.forEach((label, i) => {
    const angle = (2 * Math.PI * i) / n + Math.PI / 2;
    anchors.set(label, { x: HUB_RADIUS * Math.cos(angle), y: HUB_RADIUS * Math.sin(angle), z: 0 });
  });
  return anchors;
}

// each reel gets its OWN small anchor point near its category's spot,
// instead of every reel (and its concepts) converging on one shared
// point - this is what actually separates same-category reels into
// distinguishable sub-clusters rather than one blob.
function buildReelAnchors(nodes: GraphNode[], categoryAnchors: Map<string, Vec3>): Map<string, Vec3> {
  const anchors = new Map<string, Vec3>();
  const byCategory = new Map<string, GraphNode[]>();

  nodes.filter((n) => n.type === "reel").forEach((n) => {
    const cat = n.category || "";
    if (!byCategory.has(cat)) byCategory.set(cat, []);
    byCategory.get(cat)!.push(n);
  });

  byCategory.forEach((reels, category) => {
    const catAnchor = categoryAnchors.get(category) || { x: 0, y: 0, z: 0 };
    const n = reels.length;
    reels.forEach((reel, i) => {
      if (n === 1) {
        anchors.set(reel.id, catAnchor);
        return;
      }
      const angle = (2 * Math.PI * i) / n;
      anchors.set(reel.id, {
        x: catAnchor.x + REEL_RING_RADIUS * Math.cos(angle),
        y: catAnchor.y + REEL_RING_RADIUS * Math.sin(angle),
        z: catAnchor.z,
      });
    });
  });

  return anchors;
}

// a concept's anchor is the centroid of the reel(s) it's actually
// connected to (usually just one) - so it hugs its own reel's spot
// instead of drifting to the shared category center like every other
// concept in that category.
function buildConceptAnchors(
  edges: GraphEdge[],
  reelAnchors: Map<string, Vec3>,
  fallbackFor: (conceptId: string) => Vec3
): Map<string, Vec3> {
  const parentReelsOf = new Map<string, string[]>();
  edges.forEach((e) => {
    if (e.target.startsWith("concept:") && e.source.startsWith("reel:")) {
      if (!parentReelsOf.has(e.target)) parentReelsOf.set(e.target, []);
      parentReelsOf.get(e.target)!.push(e.source);
    }
  });

  const anchors = new Map<string, Vec3>();
  parentReelsOf.forEach((reelIds, conceptId) => {
    const positions = reelIds.map((rid) => reelAnchors.get(rid)).filter((p): p is Vec3 => !!p);
    if (positions.length === 0) {
      anchors.set(conceptId, fallbackFor(conceptId));
      return;
    }
    const avg = positions.reduce(
      (acc, p) => ({ x: acc.x + p.x / positions.length, y: acc.y + p.y / positions.length, z: acc.z + p.z / positions.length }),
      { x: 0, y: 0, z: 0 }
    );
    anchors.set(conceptId, avg);
  });

  return anchors;
}

let glowTextureCache: THREE.Texture | null = null;
function getGlowTexture(): THREE.Texture {
  if (glowTextureCache) return glowTextureCache;
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.35, "rgba(255,255,255,0.35)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  glowTextureCache = new THREE.CanvasTexture(canvas);
  return glowTextureCache;
}

const iconTextureCache = new Map<string, THREE.Texture>();
function getIconTexture(emoji: string): THREE.Texture {
  const cached = iconTextureCache.get(emoji);
  if (cached) return cached;

  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, size, size);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = `${size * 0.72}px "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif`;
  // soft dark halo so the glyph reads clearly against every node color,
  // not just the lighter ones
  ctx.shadowColor = "rgba(0,0,0,0.55)";
  ctx.shadowBlur = 10;
  ctx.fillText(emoji, size / 2, size / 2 + size * 0.04);

  const texture = new THREE.CanvasTexture(canvas);
  iconTextureCache.set(emoji, texture);
  return texture;
}

function buildNodeObject(node: any): THREE.Object3D {
  const color = colorForNode(node);
  const isUser = node.type === "user";
  const radius = Math.cbrt(node.size) * 3.2;

  const geometry = new THREE.SphereGeometry(radius, 24, 24);
  const material = new THREE.MeshStandardMaterial({
    color,
    emissive: color,
    emissiveIntensity: isUser ? 0.55 : 0.22,
    roughness: 0.35,
    metalness: 0.2,
  });
  const mesh = new THREE.Mesh(geometry, material);

  const spriteMaterial = new THREE.SpriteMaterial({
    map: getGlowTexture(),
    color,
    transparent: true,
    opacity: isUser ? 0.45 : 0.22,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const sprite = new THREE.Sprite(spriteMaterial);
  const glowScale = radius * (isUser ? 5 : 3.2);
  sprite.scale.set(glowScale, glowScale, 1);

  const group = new THREE.Group();
  group.add(sprite);
  group.add(mesh);

  const icon = iconForNode(node);
  if (icon) {
    const iconMaterial = new THREE.SpriteMaterial({
      map: getIconTexture(icon),
      transparent: true,
      depthTest: false, // always render on top of this node's own sphere
      depthWrite: false,
    });
    const iconSprite = new THREE.Sprite(iconMaterial);
    const iconScale = radius * 1.4;
    iconSprite.scale.set(iconScale, iconScale, 1);
    group.add(iconSprite);
  }

  return group;
}

export default function KnowledgeGraph({ data, onSelectReel }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphInstanceRef = useRef<any>(null);

  useEffect(() => {
    let destroyed = false;

    async function init() {
      if (!containerRef.current) return;
      const ForceGraph3D: any = (await import("3d-force-graph")).default;
      const { forceX, forceY, forceZ, forceManyBody } = await import("d3-force-3d");
      if (destroyed || !containerRef.current) return;

      const graph = ForceGraph3D()(containerRef.current)
        .backgroundColor("#0E1224")
        .showNavInfo(false)
        .nodeLabel((n: any) => n.label)
        .nodeThreeObject(buildNodeObject)
        .nodeThreeObjectExtend(false)
        .linkColor(() => "rgba(150,138,255,0.55)")
        .linkWidth((l: any) => {
          const sourceType = l.source?.type ?? "";
          const targetType = l.target?.type ?? "";
          return sourceType === "user" || targetType === "user" ? 2.5 : 1.2;
        })
        .onNodeClick((node: any) => {
          const distance = 60;
          const ratio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
          graph.cameraPosition(
            { x: (node.x || 0) * ratio, y: (node.y || 0) * ratio, z: (node.z || 0) * ratio },
            node,
            800
          );
          // both reels and concepts/products now carry a summary worth
          // showing - only category/user nodes have nothing to display
          if (node.type === "reel" || node.type === "concept") onSelectReel(node as GraphNode);
        });

      const resize = () => {
        if (containerRef.current) {
          graph.width(containerRef.current.clientWidth);
          graph.height(containerRef.current.clientHeight);
        }
      };
      resize();
      window.addEventListener("resize", resize);
      graphInstanceRef.current = { graph, resize, forceX, forceY, forceZ, forceManyBody };

      applyLayout(graph, data, forceX, forceY, forceZ, forceManyBody);
    }

    init();

    return () => {
      destroyed = true;
      if (graphInstanceRef.current) {
        window.removeEventListener("resize", graphInstanceRef.current.resize);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const inst = graphInstanceRef.current;
    if (inst?.graph) {
      applyLayout(inst.graph, data, inst.forceX, inst.forceY, inst.forceZ, inst.forceManyBody);
    }
  }, [data]);

  return <div ref={containerRef} className="absolute inset-0" />;
}

function applyLayout(graph: any, data: GraphResponse, forceX: any, forceY: any, forceZ: any, forceManyBody: any) {
  const categoryLabels = data.nodes.filter((n) => n.type === "category").map((n) => n.label);
  const categoryAnchors = buildCategoryAnchors(categoryLabels);
  const reelAnchors = buildReelAnchors(data.nodes, categoryAnchors);
  const conceptAnchors = buildConceptAnchors(data.edges, reelAnchors, (conceptId) => {
    const conceptNode = data.nodes.find((n) => n.id === conceptId);
    const cat = conceptNode?.category;
    return (cat && categoryAnchors.get(cat)) || { x: 0, y: 0, z: 0 };
  });

  const nodes = data.nodes.map((n) => {
    if (n.type === "user") return { ...n, fx: 0, fy: 0, fz: 0 };
    if (n.type === "category") {
      const a = categoryAnchors.get(n.label) || { x: 0, y: 0, z: 0 };
      return { ...n, fx: a.x, fy: a.y, fz: a.z };
    }
    return { ...n };
  });

  // 3d-force-graph MUTATES link objects in place once the simulation
  // resolves them - it replaces the string source/target with actual
  // node object references. Passing data.edges directly would corrupt
  // those same objects for every OTHER consumer of this data (e.g.
  // page.tsx's category filter, which expects source/target to stay
  // plain string ids across re-renders) - so hand the graph fresh
  // copies every time, never the shared originals.
  const links = data.edges.map((e) => ({ source: e.source, target: e.target }));
  graph.graphData({ nodes, links: links as any });

  const anchorFor = (n: any): Vec3 => {
    if (n.type === "reel") return reelAnchors.get(n.id) || { x: 0, y: 0, z: 0 };
    if (n.type === "concept") return conceptAnchors.get(n.id) || { x: 0, y: 0, z: 0 };
    return { x: 0, y: 0, z: 0 };
  };

  graph.d3Force("x", forceX((n: any) => anchorFor(n).x).strength(0.7));
  graph.d3Force("y", forceY((n: any) => anchorFor(n).y).strength(0.7));
  graph.d3Force("z", forceZ((n: any) => anchorFor(n).z).strength(0.7));
  graph.d3Force("center", null);
  graph.d3Force("charge", forceManyBody().strength(-15));

  const linkForce = graph.d3Force("link");
  if (linkForce && typeof linkForce.distance === "function") {
    linkForce.distance((l: any) => {
      const sourceType = l.source?.type ?? "";
      const targetType = l.target?.type ?? "";
      if (sourceType === "user" || targetType === "user") return HUB_RADIUS;
      if (sourceType === "category" || targetType === "category") return REEL_RING_RADIUS;
      return 10; // reel <-> concept: tight, so it's visually obvious which reel a concept belongs to
    });
  }
}