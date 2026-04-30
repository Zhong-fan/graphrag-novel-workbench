from __future__ import annotations

from collections import defaultdict

from .schema import ChapterRequest, Edge, Node, RetrievalResult, StoryGraph


class GraphRetriever:
    def retrieve(self, graph: StoryGraph, request: ChapterRequest) -> RetrievalResult:
        node_by_id = {node.id: node for node in graph.nodes}
        edges_by_node: dict[str, list[Edge]] = defaultdict(list)

        for edge in graph.edges:
            edges_by_node[edge.source].append(edge)
            edges_by_node[edge.target].append(edge)

        focus_ids = set(request.focus_characters + [request.location, request.motif])
        focus_nodes = [node_by_id[node_id] for node_id in focus_ids if node_id in node_by_id]

        related_node_ids: set[str] = set()
        related_edges: list[Edge] = []

        for node_id in focus_ids:
            for edge in edges_by_node.get(node_id, []):
                related_edges.append(edge)
                related_node_ids.add(edge.source)
                related_node_ids.add(edge.target)

        related_nodes = [
            node_by_id[node_id]
            for node_id in related_node_ids
            if node_id in node_by_id and node_id not in focus_ids
        ]

        recent_chapters = graph.chapter_history[-3:]

        return RetrievalResult(
            focus_nodes=sorted(focus_nodes, key=lambda item: item.id),
            related_nodes=sorted(related_nodes, key=lambda item: item.id),
            related_edges=related_edges,
            recent_chapters=recent_chapters,
        )
