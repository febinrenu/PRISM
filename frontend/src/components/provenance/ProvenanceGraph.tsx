"use client";

import { memo, useCallback, useEffect, useMemo, useState } from "react";
import "@xyflow/react/dist/style.css";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { ChevronRight, Minus } from "lucide-react";
import { NODE_TYPE_COLORS } from "@/lib/colors";
import { alpha, tokens } from "@/lib/tokens";
import { cn } from "@/lib/utils";
import type { GraphEdge, GraphNode } from "@/types";

/**
 * The provenance graph as a collapsible tree, read left to right:
 * document → chapter → clause → entity / rule. Only expanded branches are
 * drawn, children come in pages, so a 4,000-node graph stays legible.
 */

const RANK: Record<string, number> = { document: 0, chapter: 1, section: 2, clause: 3, entity: 4, causal: 4 };
const PAGE = 30;
const COL = 290;
const ROW = 46;

export interface TreeIndex {
  byId: Map<string, GraphNode>;
  children: Map<string, string[]>;
  parent: Map<string, string>;
  root: string | null;
  edgeLabel: Map<string, string>;
}

/** Parent of each node = its nearest structural ancestor; entities may repeat under several clauses. */
export function buildTree(nodes: GraphNode[], edges: GraphEdge[]): TreeIndex {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const best = new Map<string, string>();
  const children = new Map<string, string[]>();
  const edgeLabel = new Map<string, string>();
  const add = (p: string, c: string) => {
    const list = children.get(p) ?? [];
    list.push(c);
    children.set(p, list);
  };
  for (const e of edges) {
    const s = byId.get(e.source);
    const t = byId.get(e.target);
    if (!s || !t) continue;
    let [p, c] = [s, t];
    if (RANK[p.type] > RANK[c.type]) [p, c] = [c, p];
    if (RANK[p.type] === RANK[c.type]) continue;
    edgeLabel.set(`${p.id}>${c.id}`, e.label ?? "");
    if (c.type === "entity") {
      add(p.id, c.id);
      continue;
    }
    const cur = best.get(c.id);
    if (!cur || RANK[byId.get(cur)!.type] < RANK[p.type]) best.set(c.id, p.id);
  }
  best.forEach((p, c) => add(p, c));
  const root = nodes.find((n) => n.type === "document")?.id ?? null;
  return { byId, children, parent: best, root, edgeLabel };
}

type Data = {
  node: GraphNode;
  childCount: number;
  expanded: boolean;
  match: boolean;
  selected: boolean;
  more?: number;
};
type FlowNode = Node<Data, "prov">;

const ProvNode = memo(function ProvNode({ data }: NodeProps<FlowNode>) {
  const { node, childCount, expanded, match, selected, more } = data;
  const color = NODE_TYPE_COLORS[node.type] ?? tokens.paper[100];
  if (more !== undefined)
    return (
      <div className="flex h-9 w-[240px] items-center justify-center rounded-[4px] border border-dashed border-border-light text-[12.5px] text-text-muted hover:border-glow hover:text-text-primary">
        <Handle type="target" position={Position.Left} className="!opacity-0" isConnectable={false} />
        Show {Math.min(more, PAGE)} more of {more}
      </div>
    );
  return (
    <div
      className={cn(
        "flex h-9 w-[240px] items-center gap-2 rounded-[4px] border bg-bg-surface px-2.5 text-left transition-colors",
        selected ? "border-signal shadow-glow-sm" : match ? "border-status-warning" : "border-border hover:border-border-light"
      )}
      title={node.label}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" isConnectable={false} />
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden />
      <span className="min-w-0 flex-1 truncate text-[12.5px] text-text-primary">{node.label}</span>
      {childCount > 0 && (
        <span className="flex shrink-0 items-center gap-0.5 font-mono text-[12px] text-text-dim">
          {childCount}
          {expanded ? <Minus className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        </span>
      )}
      <Handle type="source" position={Position.Right} className="!opacity-0" isConnectable={false} />
    </div>
  );
});

const nodeTypes = { prov: ProvNode };

interface Props {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  onNodeSelect: (node: GraphNode | null) => void;
  hiddenTypes?: Set<string>;
  causalOnly?: boolean;
  nodeSearch?: string;
  selectedId?: string | null;
}

function Graph({ graphNodes, graphEdges, onNodeSelect, hiddenTypes, causalOnly = false, nodeSearch = "", selectedId }: Props) {
  const tree = useMemo(() => buildTree(graphNodes, graphEdges), [graphNodes, graphEdges]);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(tree.root ? [tree.root] : []));
  const [pages, setPages] = useState<Map<string, number>>(new Map());
  const flow = useReactFlow();

  // Which nodes may appear at all (type filters, causal-only).
  const allowed = useMemo(() => {
    const hidden = hiddenTypes ?? new Set<string>();
    let keep: Set<string> | null = null;
    if (causalOnly) {
      const k = new Set<string>();
      tree.byId.forEach((n) => {
        if (n.type !== "causal") return;
        let cur: string | undefined = n.id;
        while (cur) {
          k.add(cur);
          cur = tree.parent.get(cur);
        }
      });
      keep = k;
    }
    return (id: string) => {
      const n = tree.byId.get(id);
      if (!n) return false;
      if (n.type === "document") return true;
      if (hidden.has(n.type)) return false;
      if (keep && n.type !== "entity" && !keep.has(id)) return false;
      if (keep && n.type === "entity") return false;
      return true;
    };
  }, [tree, hiddenTypes, causalOnly]);

  // Search: highlight matches and open the branches that lead to them.
  const matches = useMemo(() => {
    const q = nodeSearch.trim().toLowerCase();
    if (q.length < 2) return new Set<string>();
    const out = new Set<string>();
    for (const n of graphNodes) {
      if (n.type !== "document" && n.label.toLowerCase().includes(q) && allowed(n.id)) out.add(n.id);
      if (out.size >= 40) break;
    }
    return out;
  }, [nodeSearch, graphNodes, allowed]);

  useEffect(() => {
    if (matches.size === 0) return;
    setExpanded((prev) => {
      const next = new Set(prev);
      matches.forEach((m) => {
        let cur = tree.parent.get(m);
        while (cur) {
          next.add(cur);
          cur = tree.parent.get(cur);
        }
      });
      return next;
    });
  }, [matches, tree]);

  const { nodes, edges } = useMemo(() => {
    const nodes: FlowNode[] = [];
    const edges: Edge[] = [];
    if (!tree.root) return { nodes, edges };
    let row = 0;
    const place = (id: string, key: string, depth: number, parentKey: string | null) => {
      const n = tree.byId.get(id)!;
      const kids = (tree.children.get(id) ?? []).filter(allowed);
      const isOpen = expanded.has(key) && kids.length > 0;
      const startRow = row;
      const childRows: number[] = [];
      if (isOpen) {
        const shown = Math.min(kids.length, PAGE * (pages.get(key) ?? 1));
        const before = row;
        for (const c of kids.slice(0, shown)) {
          const childKey = tree.byId.get(c)?.type === "entity" ? `${c}@${key}` : c;
          childRows.push(row);
          place(c, childKey, depth + 1, key);
        }
        if (shown < kids.length) {
          const moreKey = `more:${key}`;
          childRows.push(row);
          nodes.push({
            id: moreKey,
            type: "prov",
            position: { x: (depth + 1) * COL, y: row * ROW },
            data: { node: n, childCount: 0, expanded: false, match: false, selected: false, more: kids.length - shown },
          });
          edges.push({ id: `${key}>${moreKey}`, source: key, target: moreKey, style: { stroke: tokens.border.light } });
          row++;
        }
        if (row === before) row++;
      } else {
        row++;
      }
      const y = isOpen && childRows.length ? ((childRows[0] + childRows[childRows.length - 1]) / 2) * ROW : startRow * ROW;
      nodes.push({
        id: key,
        type: "prov",
        position: { x: depth * COL, y },
        data: {
          node: n,
          childCount: kids.length,
          expanded: isOpen,
          match: matches.has(id),
          selected: selectedId === id,
        },
      });
      if (parentKey) {
        const label = tree.edgeLabel.get(`${tree.byId.get(parentKey.split("@")[0])?.id}>${id}`);
        const trig = label === "triggers";
        edges.push({
          id: `${parentKey}>${key}`,
          source: parentKey,
          target: key,
          type: "smoothstep",
          style: { stroke: trig ? alpha(tokens.signal[500], 0.75) : tokens.border.light, strokeWidth: trig ? 1.5 : 1 },
        });
      }
    };
    place(tree.root, tree.root, 0, null);
    return { nodes, edges };
  }, [tree, expanded, pages, allowed, matches, selectedId]);

  // Open on the root and its first children, not the whole first page.
  const initialFit = useMemo(
    () => [{ id: tree.root ?? "" }, ...nodes.filter((n) => n.id !== tree.root).slice(0, 10).map((n) => ({ id: n.id }))],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tree]
  );

  const onNodeClick = useCallback(
    (_: unknown, n: FlowNode) => {
      if (n.data.more !== undefined) {
        const key = n.id.slice(5);
        setPages((p) => new Map(p).set(key, (p.get(key) ?? 1) + 1));
        return;
      }
      onNodeSelect(n.data.node);
      if (n.data.childCount > 0) {
        setExpanded((prev) => {
          const next = new Set(prev);
          if (next.has(n.id)) next.delete(n.id);
          else next.add(n.id);
          return next;
        });
        setTimeout(() => flow.setCenter(n.position.x + 260, n.position.y + 18, { zoom: flow.getZoom(), duration: 500 }), 30);
      }
    },
    [onNodeSelect, flow]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={onNodeClick}
      onPaneClick={() => onNodeSelect(null)}
      fitView
      fitViewOptions={{ padding: 0.2, maxZoom: 1, nodes: initialFit }}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      minZoom={0.1}
      maxZoom={2}
      className="!bg-transparent"
    >
      <Background variant={BackgroundVariant.Dots} color={tokens.border.light} gap={28} size={1} />
      <Controls showInteractive={false} position="bottom-left" />
      <MiniMap<FlowNode>
        pannable
        zoomable
        nodeColor={(n) => (n.data.more !== undefined ? "var(--ink-600)" : NODE_TYPE_COLORS[n.data.node.type] ?? tokens.text.primary)}
        maskColor={alpha(tokens.bg.deep, 0.8)}
        className="!hidden md:!block"
      />
    </ReactFlow>
  );
}

export default function ProvenanceGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <Graph {...props} />
    </ReactFlowProvider>
  );
}
