"use client";

/**
 * The provenance graph as strata in 3D: the document on top, then its
 * chapters, its clauses, the condition → consequence rules found in them and
 * the entities they name, each layer a ring under its parent. Orbit to read
 * it from any side; click a node to open it. Loaded only on demand.
 */
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { Canvas, type ThreeEvent } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useTokens } from "@/design/theme";
import type { GraphEdge, GraphNode } from "@/types";

const LEVEL: Record<string, number> = { document: 3.4, chapter: 1.8, section: 1.0, clause: 0, causal: -1.6, entity: -3.0 };
const RADIUS: Record<string, number> = { document: 0, chapter: 2.6, section: 3.4, clause: 4.6, causal: 5.4, entity: 6.2 };

function hash(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return ((h >>> 0) % 10000) / 10000;
}

function useLayout(nodes: GraphNode[], edges: GraphEdge[]) {
  return useMemo(() => {
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const parent = new Map<string, string>();
    for (const e of edges) {
      const s = byId.get(e.source);
      const t = byId.get(e.target);
      if (!s || !t) continue;
      if (t.type === "entity") continue; // entities are shared, not children
      const prev = parent.get(t.id);
      // a chapter beats the document as a clause's parent
      if (!prev || (byId.get(prev)?.type === "document" && s.type !== "document")) parent.set(t.id, s.id);
    }
    const kids = new Map<string, string[]>();
    parent.forEach((p, c) => kids.set(p, [...(kids.get(p) ?? []), c]));
    const angle = new Map<string, number>();
    const root = nodes.find((n) => n.type === "document");
    // angular sectors by leaf count, so big chapters get room
    const leaves = new Map<string, number>();
    const count = (id: string): number => {
      if (leaves.has(id)) return leaves.get(id)!;
      const c = kids.get(id) ?? [];
      const v = c.length ? c.reduce((s, k) => s + count(k), 0) : 1;
      leaves.set(id, v);
      return v;
    };
    const place = (id: string, a0: number, a1: number) => {
      angle.set(id, (a0 + a1) / 2);
      let a = a0;
      const total = count(id);
      for (const k of kids.get(id) ?? []) {
        const span = ((a1 - a0) * count(k)) / total;
        place(k, a, a + span);
        a += span;
      }
    };
    if (root) place(root.id, 0, Math.PI * 2);
    const ents = nodes.filter((n) => n.type === "entity");
    ents.forEach((n, i) => angle.set(n.id, (i / Math.max(1, ents.length)) * Math.PI * 2));
    const pos = new Map<string, THREE.Vector3>();
    for (const n of nodes) {
      const a = angle.get(n.id) ?? hash(n.id) * Math.PI * 2;
      const r = (RADIUS[n.type] ?? 4) * (n.type === "clause" || n.type === "causal" ? 0.9 + 0.2 * hash(n.id) : 1);
      const y = (LEVEL[n.type] ?? 0) + (n.type === "clause" ? (hash(n.id + "y") - 0.5) * 0.35 : 0);
      pos.set(n.id, new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r));
    }
    return { pos, parent, byId };
  }, [nodes, edges]);
}

const disc = (() => {
  if (typeof document === "undefined") return null;
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, "rgba(255,255,255,1)");
  grd.addColorStop(0.55, "rgba(255,255,255,0.9)");
  grd.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
})();

function Nodes({
  nodes,
  layout,
  hidden,
  selectedId,
  onSelect,
}: {
  nodes: GraphNode[];
  layout: ReturnType<typeof useLayout>;
  hidden: Set<string>;
  selectedId: string | null;
  onSelect: (n: GraphNode | null) => void;
}) {
  const tokens = useTokens();
  const NODE_TYPE_COLORS = tokens.node as Record<string, string>;
  const [hover, setHover] = useState<number | null>(null);
  const shown = useMemo(() => nodes.filter((n) => !hidden.has(n.type)), [nodes, hidden]);
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const p = new Float32Array(shown.length * 3);
    const c = new Float32Array(shown.length * 3);
    const col = new THREE.Color();
    shown.forEach((n, i) => {
      const v = layout.pos.get(n.id)!;
      p.set([v.x, v.y, v.z], i * 3);
      col.set(NODE_TYPE_COLORS[n.type] ?? tokens.text.dim);
      if (n.id === selectedId) col.set(tokens.signal[500]);
      c.set([col.r, col.g, col.b], i * 3);
    });
    g.setAttribute("position", new THREE.BufferAttribute(p, 3));
    g.setAttribute("color", new THREE.BufferAttribute(c, 3));
    return g;
  }, [shown, layout, selectedId, tokens, NODE_TYPE_COLORS]);
  const h = hover !== null ? shown[hover] : null;
  return (
    <>
      <points
        geometry={geo}
        onPointerMove={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          setHover(e.index ?? null);
        }}
        onPointerOut={() => setHover(null)}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          if (e.index !== undefined) onSelect(shown[e.index]);
        }}
      >
        <pointsMaterial vertexColors size={0.16} sizeAttenuation map={disc ?? undefined} transparent alphaTest={0.05} depthWrite={false} />
      </points>
      {h && (
        <Html position={layout.pos.get(h.id)!} center style={{ pointerEvents: "none" }}>
          <div className="-translate-y-6 whitespace-nowrap rounded-[4px] border border-border-light bg-bg-overlay/95 px-2 py-1 text-[12px] text-text-primary shadow-lift">
            {h.label}
            <span className="ml-1.5 font-mono text-[12px] text-text-dim">{h.type}</span>
          </div>
        </Html>
      )}
    </>
  );
}

function Edges({
  edges,
  layout,
  hidden,
  selectedId,
}: {
  edges: GraphEdge[];
  layout: ReturnType<typeof useLayout>;
  hidden: Set<string>;
  selectedId: string | null;
}) {
  const tokens = useTokens();
  const { all, focus } = useMemo(() => {
    const tree: number[] = [];
    const hot: number[] = [];
    layout.parent.forEach((p, c) => {
      const a = layout.pos.get(p);
      const b = layout.pos.get(c);
      const tp = layout.byId.get(p)?.type ?? "";
      const tc = layout.byId.get(c)?.type ?? "";
      if (!a || !b || hidden.has(tp) || hidden.has(tc)) return;
      (c === selectedId || p === selectedId ? hot : tree).push(a.x, a.y, a.z, b.x, b.y, b.z);
    });
    if (selectedId) {
      // the selected node's entity links, which the tree leaves out
      for (const e of edges) {
        if (e.source !== selectedId && e.target !== selectedId) continue;
        const a = layout.pos.get(e.source);
        const b = layout.pos.get(e.target);
        if (a && b) hot.push(a.x, a.y, a.z, b.x, b.y, b.z);
      }
    }
    const mk = (arr: number[]) => {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(arr), 3));
      return g;
    };
    return { all: mk(tree), focus: mk(hot) };
  }, [layout, edges, hidden, selectedId]);
  return (
    <>
      <lineSegments geometry={all}>
        <lineBasicMaterial color={tokens.paper[100]} transparent opacity={0.09} depthWrite={false} />
      </lineSegments>
      <lineSegments geometry={focus}>
        <lineBasicMaterial color={tokens.signal[500]} transparent opacity={0.9} depthWrite={false} />
      </lineSegments>
    </>
  );
}

function LayerRings() {
  const tokens = useTokens();
  const NODE_TYPE_COLORS = tokens.node as Record<string, string>;
  const rings = useMemo(
    () =>
      (["chapter", "clause", "causal", "entity"] as const).map((t) => {
        const pts: THREE.Vector3[] = [];
        for (let i = 0; i <= 128; i++) {
          const a = (i / 128) * Math.PI * 2;
          pts.push(new THREE.Vector3(Math.cos(a) * RADIUS[t], LEVEL[t], Math.sin(a) * RADIUS[t]));
        }
        return { t, geo: new THREE.BufferGeometry().setFromPoints(pts) };
      }),
    []
  );
  return (
    <>
      {rings.map(({ t, geo }) => (
        <lineLoop key={t} geometry={geo}>
          <lineBasicMaterial color={NODE_TYPE_COLORS[t] ?? tokens.text.dim} transparent opacity={0.18} />
        </lineLoop>
      ))}
    </>
  );
}

export default function ProvenanceStrata({
  graphNodes,
  graphEdges,
  hiddenTypes,
  selectedId,
  onNodeSelect,
}: {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  hiddenTypes: Set<string>;
  selectedId: string | null;
  onNodeSelect: (n: GraphNode | null) => void;
}) {
  const layout = useLayout(graphNodes, graphEdges);
  const tokens = useTokens();
  const interacted = useRef(false);
  const [rotate, setRotate] = useState(true);
  return (
    <div className="absolute inset-0" aria-label="The provenance graph in three dimensions" role="img">
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [0, 6, 13], fov: 40 }}
        gl={{ antialias: true, alpha: false }}
        onCreated={({ gl }) => gl.setClearColor(tokens.bg.base)}
        key={tokens.bg.base}
        raycaster={{ params: { Points: { threshold: 0.12 } } as THREE.RaycasterParameters }}
        onPointerMissed={() => onNodeSelect(null)}
      >
        <Nodes nodes={graphNodes} layout={layout} hidden={hiddenTypes} selectedId={selectedId} onSelect={onNodeSelect} />
        <Edges edges={graphEdges} layout={layout} hidden={hiddenTypes} selectedId={selectedId} />
        <LayerRings />
        <OrbitControls
          enableDamping
          autoRotate={rotate}
          autoRotateSpeed={0.35}
          minDistance={4}
          maxDistance={30}
          onStart={() => {
            if (!interacted.current) {
              interacted.current = true;
              setRotate(false);
            }
          }}
        />
      </Canvas>
      <div className="pointer-events-none absolute bottom-3 left-4 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[12px] text-text-muted">
        <span>top to bottom: document · chapters · clauses · rules · entities</span>
        <span className="text-text-dim">drag to orbit · scroll to zoom · click a node</span>
      </div>
    </div>
  );
}
