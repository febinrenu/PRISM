"use client";
import { useMemo, useCallback } from "react";
import "@xyflow/react/dist/style.css";
import {
  ReactFlow as ReactFlowTyped,
  Background,
  Controls,
  Node,
  Edge,
  NodeTypes,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from "@xyflow/react";
// Cast to any to avoid @xyflow/react v12 JSX type mismatch
const ReactFlow = ReactFlowTyped as any;
import { useDocumentStore } from "@/hooks/useDocumentStore";
import { ENTITY_COLORS } from "@/lib/colors";
import { tokens, alpha } from "@/lib/tokens";

interface EntityNodeData {
  label: string;
  entityLabel: string;
  count: number;
}

function EntityNode({ data }: { data: EntityNodeData }) {
  const colors = (ENTITY_COLORS as Record<string, typeof ENTITY_COLORS["OBLIGATION"]>)[data.entityLabel] || ENTITY_COLORS["OBLIGATION"];
  const size = Math.max(36, Math.min(64, 36 + data.count * 3));
  return (
    <div
      className="flex items-center justify-center rounded-full font-mono font-bold transition-all duration-150 cursor-pointer"
      style={{
        width: size, height: size,
        background: colors.bg,
        border: `2px solid ${colors.border}`,
        color: colors.text,
        fontSize: Math.max(8, Math.min(11, 8 + data.count)),
        textAlign: "center",
        padding: "4px",
        lineHeight: "1.2",
        boxShadow: `0 0 12px ${colors.border}`,
      }}
      title={`${data.label} (×${data.count})`}
    >
      <span className="truncate px-1" style={{ maxWidth: size - 12 }}>
        {data.label.length > 10 ? data.label.slice(0, 9) + "…" : data.label}
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
        if (!entityFreq[key]) entityFreq[key] = { count: 0, label: e.text, type: e.label };
        entityFreq[key].count++;
        if (!seen.has(key)) seen.add(key);
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
      .slice(0, 30);

    const topKeys = new Set(top.map(([k]) => k));

    const nodes: Node[] = top.map(([key, info], i) => {
      const angle = (i / top.length) * 2 * Math.PI - Math.PI / 2;
      const r = 180;
      return {
        id: key,
        type: "entityNode",
        position: { x: 250 + r * Math.cos(angle), y: 220 + r * Math.sin(angle) },
        data: { label: info.label, entityLabel: info.type as string, count: info.count },
      };
    });

    const edges: Edge[] = Object.entries(cooccurrence)
      .filter(([edgeKey]) => {
        const [a, b] = edgeKey.split("|||");
        return topKeys.has(a) && topKeys.has(b);
      })
      .sort((a, b) => b[1] - a[1])
      .slice(0, 40)
      .map(([edgeKey, count]) => {
        const [a, b] = edgeKey.split("|||");
        return {
          id: edgeKey,
          source: a, target: b,
          style: { stroke: alpha(tokens.accent.primary, 0.25), strokeWidth: Math.min(count * 0.8, 4) },
          animated: false,
        };
      });

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
    <div className="p-4 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-mono uppercase tracking-widest text-text-muted">Entity Co-occurrence</p>
        <p className="text-[10px] font-mono text-text-dim">Click node to filter clauses</p>
      </div>
      <div className="rounded-xl overflow-hidden border border-border" style={{ height: 340 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
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
      <p className="text-[10px] font-mono text-text-dim">Node size = frequency · Edge thickness = co-occurrence</p>
    </div>
  );
}
