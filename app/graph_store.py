from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .schema import ChapterRecord, Edge, Node, StoryGraph
from .storage import read_json, write_json


class GraphStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> StoryGraph:
        payload = read_json(self.path)
        return StoryGraph(
            project=payload["project"],
            nodes=[Node(**node) for node in payload["nodes"]],
            edges=[Edge(**edge) for edge in payload["edges"]],
            chapter_history=[
                ChapterRecord(**record) for record in payload.get("chapter_history", [])
            ],
        )

    def save(self, graph: StoryGraph) -> None:
        payload = {
            "project": graph.project,
            "nodes": [asdict(node) for node in graph.nodes],
            "edges": [asdict(edge) for edge in graph.edges],
            "chapter_history": [asdict(record) for record in graph.chapter_history],
        }
        write_json(self.path, payload)

    @staticmethod
    def upsert_node(graph: StoryGraph, node: Node) -> None:
        for index, current in enumerate(graph.nodes):
            if current.id == node.id:
                graph.nodes[index] = node
                return
        graph.nodes.append(node)

    @staticmethod
    def append_edge(graph: StoryGraph, edge: Edge) -> None:
        for current in graph.edges:
            if (
                current.source == edge.source
                and current.target == edge.target
                and current.type == edge.type
                and current.attributes == edge.attributes
            ):
                return
        graph.edges.append(edge)

    @staticmethod
    def remove_node_and_incident_edges(graph: StoryGraph, node_id: str) -> None:
        graph.nodes = [node for node in graph.nodes if node.id != node_id]
        graph.edges = [
            edge for edge in graph.edges if edge.source != node_id and edge.target != node_id
        ]
