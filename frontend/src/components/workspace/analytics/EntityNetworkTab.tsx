"use client";
import { useMemo, useCallback } from "react";
import "@xyflow/react/dist/style.css";
import {
  ReactFlow as ReactFlowTyped,
  Background,
  Controls,
  Handle,
  Position,
  Node,
  Edge,
  NodeTypes,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from "@xyflow/react";
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from "d3";
// Cast to any to avoid @xyflow/react v12 JSX type mismatch
const ReactFlow = ReactFlowTyped as any;
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { ENTITY_COLORS } from "@/lib/colors";
import { tokens, alpha } from "@/lib/tokens";

interface EntityNodeData {
  label: string;
  entityLabel: string;
  count: number;
  size: number;
}

/** Width reserved under each circle for its label. */
const LABEL_W = 124;
const TOP_N = 24;

// both handles sit on the circle's centre, so edges run centre to centre
const centreHandle = (size: number) => ({
  top: size / 2,
  left: "50%",
  width: 1,
  height: 1,
  minWidth: 0,
  minHeight: 0,
  border: 0,
  opacity: 0,
});

function EntityNode({ data }: { data: EntityNodeData }) {
  const colors = (ENTITY_COLORS as Record<string, typeof ENTITY_COLORS["OBLIGATION"]>)[data.entityLabel] || ENTITY_COLORS["OBLIGATION"];
  return (
    <div className="flex cursor-pointer flex-col items-center gap-1" style={{ width: LABEL_W }} title={`${data.label} · ${data.entityLabel.toLowerCase()} · in ${data.count} clauses`}>
      <Handle type="target" position={Position.Top} style={centreHandle(data.size)} isConnectable={false} />
      <Handle type="source" position={Position.Top} style={centreHandle(data.size)} isConnectable={false} />
      <div
        className="flex items-center justify-center rounded-full font-mono text-[12px] font-semibold tabular-nums transition-transform duration-150 hover:scale-105"
        style={{
          width: data.size,
          height: data.size,
          background: colors.bg,
          border: `2px solid ${colors.border}`,
          color: colors.text,
        }}
      >
        {data.count}
      </div>
      <span className="max-w-full truncate rounded-[3px] bg-bg-base/80 px-1 text-[12px] leading-tight text-text-secondary">
        {data.label}
      </span>
    </div>
  );
}

const nodeTypes: NodeTypes = { entityNode: EntityNode as any };

export default function EntityNetworkTab() {
  const { clauses, setHighlightedEntityKey } = useDocumentStore();

  const { initialNodes, initialEdges } = useMemo(() => {
    const entityFreq: Record<string, { count: number; label: string; type: string }> = {};
    const cooccurrence: Record<string, number> = {};

    for (const clause of clauses) {
      const seen = new Set<string>();
      for (const e of clause.entities) {
        const key = `${e.label}::${e.text.toLowerCase()}`;
        if (seen.has(key)) continue; // count clauses, not repeat mentions
        if (!entityFreq[key]) entityFreq[key] = { count: 0, label: e.text, type: e.label };
        entityFreq[key].count++;
        seen.add(key);
      }
      const arr = Array.from(seen);
      for (let i = 0; i < arr.length; i++) {
        for (let j = i + 1; j < arr.length; j++) {
          const edgeKey = [arr[i], arr[j]].sort().join("|||");
          cooccurrence[edgeKey] = (cooccurrence[edgeKey] || 0) + 1;
        }
      }
    }

    const top = Object.entries(entityFreq)
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, TOP_N);
    const topKeys = new Set(top.map(([k]) => k));
    const maxCount = Math.max(1, ...top.map(([, v]) => v.count));

    const links = Object.entries(cooccurrence)
      .filter(([edgeKey]) => {
        const [a, b] = edgeKey.split("|||");
        return topKeys.has(a) && topKeys.has(b);
      })
      .sort((a, b) => b[1] - a[1])
      .slice(0, 48)
      .map(([edgeKey, count]) => {
        const [a, b] = edgeKey.split("|||");
        return { id: edgeKey, source: a, target: b, count };
      });

    // A force layout: entities that appear together sit together, and every
    // node keeps clear of its neighbours' labels. Run to rest up front, so
    // the picture never wobbles.
    type Sim = { id: string; size: number; x?: number; y?: number };
    const sim: Sim[] = top.map(([key, info], i) => {
      const angle = (i / top.length) * 2 * Math.PI;
      return {
        id: key,
        size: Math.round(30 + 26 * Math.sqrt(info.count / maxCount)),
        x: 220 * Math.cos(angle),
        y: 220 * Math.sin(angle),
      };
    });
    const simLinks = links.map((l) => ({ source: l.source, target: l.target, count: l.count }));
    forceSimulation(sim as any)
      .force("charge", forceManyBody().strength(-260))
      .force("link", forceLink(simLinks as any).id((d: any) => d.id).distance(130).strength(0.15))
      .force("collide", forceCollide((d: any) => Math.max(LABEL_W / 2, d.size / 2 + 12) + 6).iterations(3))
      .force("x", forceX(0).strength(0.06))
      .force("y", forceY(0).strength(0.09))
      .stop()
      .tick(320);

    const nodes: Node[] = top.map(([key, info], i) => ({
      id: key,
      type: "entityNode",
      // React Flow places the top-left corner; the layout gave circle centres
      position: { x: (sim[i].x ?? 0) - LABEL_W / 2, y: (sim[i].y ?? 0) - sim[i].size / 2 },
      data: { label: info.label, entityLabel: info.type as string, count: info.count, size: sim[i].size },
    }));

    const maxEdge = Math.max(1, ...links.map((l) => l.count));
    const edges: Edge[] = links.map((l) => ({
      id: l.id,
      source: l.source,
      target: l.target,
      type: "straight",
      style: {
        stroke: alpha(tokens.text.muted, 0.25 + 0.4 * (l.count / maxEdge)),
        strokeWidth: 1 + 3 * (l.count / maxEdge),
      },
    }));

    return { initialNodes: nodes, initialEdges: edges };
  }, [clauses]);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setHighlightedEntityKey(node.id);
  }, [setHighlightedEntityKey]);

  if (clauses.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted">
        <p className="font-mono text-sm">Waiting for analysis…</p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-xs font-mono uppercase tracking-widest text-text-muted">Entity co-occurrence</p>
        <p className="text-micro font-mono text-text-dim">Click an entity to filter the clauses · drag to rearrange</p>
      </div>
      <div className="min-h-[420px] flex-1 overflow-hidden rounded-xl border border-border">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.08 }}
          minZoom={0.3}
          maxZoom={3}
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color={tokens.border.DEFAULT} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <p className="text-micro font-mono text-text-dim">
        The {TOP_N} most frequent entities · circle size and number = clauses mentioning it · line weight = clauses where two appear together
      </p>
    </div>
  );
}
