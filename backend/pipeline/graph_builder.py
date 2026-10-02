"""
Provenance graph builder using NetworkX.
Constructs a hierarchical knowledge graph:
  Document → Chapter → Section → Clause → Entity → CausalPattern
"""
import networkx as nx
from collections import defaultdict
from models.schemas import Clause, GraphNode, GraphEdge, GraphData


def build_provenance_graph(clauses: list[Clause], doc_id: str, doc_name: str = "") -> GraphData:
    """
    Build the provenance graph from processed clauses.
    Returns GraphData with nodes and edges suitable for React Flow.
    """
    G = nx.DiGraph()
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    edge_set: set[tuple[str, str]] = set()

    def add_node(node_id: str, node_type: str, label: str, data: dict):
        if not G.has_node(node_id):
            G.add_node(node_id, type=node_type, label=label, data=data)
            nodes.append(GraphNode(id=node_id, type=node_type, label=label, data=data))

    def add_edge(src: str, tgt: str, label: str = ""):
        key = (src, tgt)
        if key not in edge_set:
            edge_set.add(key)
            edge_id = f"e_{src}_{tgt}".replace(" ", "_")[:80]
            G.add_edge(src, tgt)
            edges.append(GraphEdge(id=edge_id, source=src, target=tgt, label=label))

    # Document root node
    doc_node_id = f"doc_{doc_id}"
    add_node(doc_node_id, "document", doc_name or f"Document {doc_id[:8]}", {
        "doc_id": doc_id,
        "clause_count": len(clauses),
    })

    # Track chapter and section nodes to avoid duplicates
    chapter_nodes: dict[str, str] = {}   # chapter_key -> node_id
    section_nodes: dict[str, str] = {}   # section_key -> node_id

    # Entity deduplication: (text.lower(), label) -> entity node_id
    entity_nodes: dict[tuple[str, str], str] = {}
    entity_counts: dict[tuple[str, str], int] = defaultdict(int)

    for clause in clauses:
        hierarchy = clause.section_hierarchy or []

        # Chapter node (first level of hierarchy)
        if hierarchy:
            chapter_key = hierarchy[0]
            if chapter_key not in chapter_nodes:
                ch_id = f"ch_{doc_id}_{chapter_key}"
                add_node(ch_id, "chapter", f"Chapter {chapter_key}", {"number": chapter_key})
                add_edge(doc_node_id, ch_id, "contains")
                chapter_nodes[chapter_key] = ch_id
            parent_id = chapter_nodes[chapter_key]
        else:
            parent_id = doc_node_id

        # Section node (second level of hierarchy)
        if len(hierarchy) >= 2:
            section_key = ".".join(hierarchy[:2])
            if section_key not in section_nodes:
                sec_id = f"sec_{doc_id}_{section_key}"
                add_node(sec_id, "section", f"§{section_key}", {"number": section_key})
                add_edge(parent_id, sec_id, "contains")
                section_nodes[section_key] = sec_id
            parent_id = section_nodes[section_key]

        # Clause node
        clause_id = clause.clause_id
        clause_preview = clause.text[:80].replace('"', "'") + ("..." if len(clause.text) > 80 else "")
        add_node(clause_id, "clause", f"Clause {clause_id.split('_')[-1]}", {
            "text_preview": clause_preview,
            "page": clause.page,
            "entity_count": len(clause.entities),
            "complexity_score": round(clause.complexity_score, 3),
        })
        add_edge(parent_id, clause_id, "contains")

        # Entity nodes
        for entity in clause.entities:
            entity_key = (entity.text.lower()[:50], entity.label)
            entity_counts[entity_key] += 1
            if entity_key not in entity_nodes:
                ent_id = f"ent_{entity.label}_{entity.text[:30].replace(' ', '_').replace('.', '')}_{len(entity_nodes)}"
                add_node(ent_id, "entity", entity.text[:40], {
                    "label": entity.label,
                    "text": entity.text,
                    "frequency": 1,
                })
                entity_nodes[entity_key] = ent_id
            ent_id = entity_nodes[entity_key]
            add_edge(clause_id, ent_id, entity.label.lower())

        # Causal pattern nodes
        for i, cp in enumerate(clause.causal_patterns):
            cp_id = f"causal_{clause_id}_{i}"
            add_node(cp_id, "causal", cp.pattern_type.replace("_", " "), {
                "pattern_type": cp.pattern_type,
                "condition": cp.condition_span[:100],
                "action": cp.action_span[:100],
                "confidence": cp.confidence,
                "source_clause_id": clause_id,
                "page": clause.page,
            })
            add_edge(clause_id, cp_id, "triggers")

    # Update entity frequency counts
    for node in nodes:
        if node.type == "entity":
            text_lower = node.data.get("text", "")[:50].lower()
            label = node.data.get("label", "")
            key = (text_lower, label)
            node.data["frequency"] = entity_counts.get(key, 1)

    return GraphData(nodes=nodes, edges=edges)
