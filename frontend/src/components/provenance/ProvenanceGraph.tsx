"use client";
import { useMemo, useCallback, useEffect, type CSSProperties, type MouseEvent } from "react";
import "@xyflow/react/dist/style.css";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
  BackgroundVariant,
  MarkerType,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import { NODE_TYPE_COLORS } from "@/lib/colors";
import { tokens, alpha } from "@/lib/tokens";
import type { GraphNode, GraphEdge } from "@/types";

const NODE_SHAPES: Record<string, { bg: string; border: string }> = {
  document: { bg: alpha(tokens.node.document, 0.15), border: alpha(tokens.node.document, 0.5) },
  chapter:  { bg: alpha(tokens.node.chapter, 0.15),  border: alpha(tokens.node.chapter, 0.5)  },
  section:  { bg: alpha(tokens.node.section, 0.12),  border: alpha(tokens.node.section, 0.4)  },
  clause:   { bg: alpha(tokens.bg.surface, 0.8),     border: tokens.border.DEFAULT             },
  entity:   { bg: alpha(tokens.node.entity, 0.12),   border: alpha(tokens.node.entity, 0.4)   },
  causal:   { bg: alpha(tokens.node.causal, 0.12),   border: alpha(tokens.node.causal, 0.4)   },
};

const NODE_SIZES: Record<string, { width: number; height: number }> = {
  document: { width: 160, height: 60 },
  chapter:  { width: 120, height: 48 },
  section:  { width: 110, height: 44 },
  clause:   { width: 180, height: 64 },
  entity:   { width: 100, height: 40 },
  causal:   { width: 130, height: 48 },
};

// ── Custom node ───────────────────────────────────────────────────────────────
export type PrismNodeData = {
  nodeType: GraphNode["type"];
  label: string;
  color: string;
  maxWidth: number;
  entityCount?: number;
  frequency?: number;
  raw: GraphNode;
};

type PrismFlowNode = Node<PrismNodeData, "prism">;

const HANDLE_STYLE: CSSProperties = {
  opacity: 0,
  width: 4,
  height: 4,
  minWidth: 0,
  minHeight: 0,
  border: "none",
  background: "transparent",
  pointerEvents: "none",
};

function PrismNode({ data }: NodeProps<PrismFlowNode>) {
  return (
    <>
      <Handle type="target" position={Position.Top} style={HANDLE_STYLE} isConnectable={false} />
      <div className="text-center px-2" style={{ maxWidth: data.maxWidth }}>
        <div
          className="text-[8px] font-mono mb-0.5 uppercase tracking-widest"
          style={{ color: `${data.color}AA` }}
        >
          {data.nodeType}
        </div>
        <div className="text-xs font-display font-medium truncate text-text-primary">
          {data.label}
        </div>
        {data.entityCount !== undefined && (
          <div className="text-[9px] text-text-muted">{data.entityCount} entities</div>
        )}
        {data.frequency !== undefined && data.frequency > 1 && (
          <div className="text-[9px] text-text-muted">×{data.frequency}</div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={HANDLE_STYLE} isConnectable={false} />
    </>
  );
}

// Module-level so the object identity is stable across renders.
const nodeTypes = { prism: PrismNode };

// ── Graph building ────────────────────────────────────────────────────────────
const TYPE_ORDER = ["document", "chapter", "section", "clause", "entity", "causal"];

function buildFlowNodes(graphNodes: GraphNode[]): PrismFlowNode[] {
  const byType: Record<string, GraphNode[]> = {};
  graphNodes.forEach((n) => {
    if (!byType[n.type]) byType[n.type] = [];
    byType[n.type].push(n);
  });

  const VERTICAL_SPACING = 120;
  const HORIZONTAL_SPACING = 220;

  const nodes: PrismFlowNode[] = [];

  TYPE_ORDER.forEach((type, rowIdx) => {
    const items = byType[type] || [];
    const rowWidth = items.length * HORIZONTAL_SPACING;
    items.forEach((item, colIdx) => {
      const shape = NODE_SHAPES[type] || NODE_SHAPES.clause;
      const size = NODE_SIZES[type] || NODE_SIZES.clause;
      const color = NODE_TYPE_COLORS[type] || tokens.accent.primary;

      nodes.push({
        id: item.id,
        position: {
          x: colIdx * HORIZONTAL_SPACING - rowWidth / 2 + HORIZONTAL_SPACING / 2,
          y: rowIdx * VERTICAL_SPACING,
        },
        data: {
          nodeType: item.type,
          label: item.label,
          color,
          maxWidth: size.width - 16,
          entityCount:
            typeof item.data.entity_count === "number" ? item.data.entity_count : undefined,
          frequency: typeof item.data.frequency === "number" ? item.data.frequency : undefined,
          raw: item,
        },
        style: {
          width: size.width,
          height: size.height,
          background: shape.bg,
          border: `1px solid ${shape.border}`,
          borderRadius: type === "entity" ? "50%" : type === "causal" ? "8px" : "12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
        },
        type: "prism",
      });
    });
  });

  return nodes;
}

function buildFlowEdges(graphEdges: GraphEdge[]): Edge[] {
  return graphEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    labelStyle: { fill: tokens.text.muted, fontSize: 9, fontFamily: "JetBrains Mono" },
    style: {
      stroke: e.label === "triggers" ? alpha(tokens.accent.primary, 0.5) : alpha(tokens.accent.primary, 0.2),
      strokeWidth: e.label === "triggers" ? 2 : 1,
      strokeDasharray: e.label === "triggers" ? "4 2" : "none",
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: e.label === "triggers" ? alpha(tokens.accent.primary, 0.7) : alpha(tokens.accent.primary, 0.4),
    },
    animated: e.label === "triggers",
    type: "default",
  }));
}

// ── Visibility filtering ──────────────────────────────────────────────────────
const ANCESTOR_TYPES = new Set(["document", "chapter", "section"]);

function computeVisibleIds(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[],
  hiddenTypes: Set<string>,
  causalOnly: boolean,
  search: string
): Set<string> {
  const typeById = new Map(graphNodes.map((n) => [n.id, n.type]));

  // "Causal only": causal nodes + clauses connected to them + those clauses' ancestors.
  let causalScope: Set<string> | null = null;
  if (causalOnly) {
    causalScope = new Set<string>();
    graphNodes.forEach((n) => {
      if (n.type === "causal") causalScope!.add(n.id);
    });
    graphEdges.forEach((e) => {
      const st = typeById.get(e.source);
      const tt = typeById.get(e.target);
      if (st === "clause" && tt === "causal") causalScope!.add(e.source);
      if (st === "causal" && tt === "clause") causalScope!.add(e.target);
    });
    // Walk structural edges upward until fixpoint to include ancestors.
    let changed = true;
    while (changed) {
      changed = false;
      for (const e of graphEdges) {
        const st = typeById.get(e.source);
        if (
          st !== undefined &&
          ANCESTOR_TYPES.has(st) &&
          causalScope.has(e.target) &&
          !causalScope.has(e.source)
        ) {
          causalScope.add(e.source);
          changed = true;
        }
      }
    }
  }

  const q = search.trim().toLowerCase();
  const visible = new Set<string>();
  graphNodes.forEach((n) => {
    // Document root is always visible so the graph never loses its anchor.
    if (n.type === "document") {
      visible.add(n.id);
      return;
    }
    if (hiddenTypes.has(n.type)) return;
    if (causalScope && !causalScope.has(n.id)) return;
    if (q && !n.label.toLowerCase().includes(q)) return;
    visible.add(n.id);
  });
  return visible;
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function ProvenanceGraph({
  graphNodes,
  graphEdges,
  onNodeSelect,
  hiddenTypes,
  causalOnly = false,
  nodeSearch = "",
}: {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  onNodeSelect: (node: GraphNode | null) => void;
  hiddenTypes?: Set<string>;
  causalOnly?: boolean;
  nodeSearch?: string;
}) {
  const initialNodes = useMemo(() => buildFlowNodes(graphNodes), [graphNodes]);
  const initialEdges = useMemo(() => buildFlowEdges(graphEdges), [graphEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState<PrismFlowNode>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdges);

  const visibleIds = useMemo(
    () =>
      computeVisibleIds(
        graphNodes,
        graphEdges,
        hiddenTypes ?? new Set<string>(),
        causalOnly,
        nodeSearch
      ),
    [graphNodes, graphEdges, hiddenTypes, causalOnly, nodeSearch]
  );

  // Toggle `hidden` in place — keeps positions (and any drags) stable.
  useEffect(() => {
    setNodes((nds) => nds.map((n) => ({ ...n, hidden: !visibleIds.has(n.id) })));
    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        hidden: !visibleIds.has(e.source) || !visibleIds.has(e.target),
      }))
    );
  }, [visibleIds, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: MouseEvent, node: PrismFlowNode) => {
      onNodeSelect(node.data.raw);
    },
    [onNodeSelect]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={onNodeClick}
      onPaneClick={() => onNodeSelect(null)}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      proOptions={{ hideAttribution: true }}
      style={{ background: "transparent" }}
      nodesDraggable
      nodesConnectable={false}
      minZoom={0.05}
      maxZoom={4}
    >
      <Background variant={BackgroundVariant.Dots} color={tokens.border.DEFAULT} gap={32} size={1} />
      <Controls />
      <MiniMap<PrismFlowNode>
        nodeColor={(n) => NODE_TYPE_COLORS[n.data.nodeType] ?? tokens.accent.primary}
        maskColor={alpha(tokens.bg.deep, 0.85)}
      />
    </ReactFlow>
  );
}
