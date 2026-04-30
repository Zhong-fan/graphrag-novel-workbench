from __future__ import annotations

import json

from neo4j import GraphDatabase

from .schema import ChapterRecord, Edge, Node, StoryGraph


class Neo4jGraphStore:
    def __init__(
        self,
        *,
        uri: str,
        user: str,
        password: str,
        database: str,
    ) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def exists(self) -> bool:
        query = "MATCH (p) WHERE 'ProjectMeta' IN labels(p) RETURN count(p) > 0 AS exists"
        with self.driver.session(database=self.database) as session:
            return bool(session.run(query).single()["exists"])

    def load(self) -> StoryGraph:
        with self.driver.session(database=self.database) as session:
            project_record = session.run(
                """
                MATCH (p)
                WHERE 'ProjectMeta' IN labels(p)
                RETURN properties(p) AS props
                """
            ).single()
            if project_record is None:
                raise RuntimeError("Neo4j 中不存在项目元数据，请先初始化图谱。")

            node_records = session.run(
                """
                MATCH (n:StoryNode)
                RETURN n.id AS id, n.type AS type, n.name AS name, n.attributes_json AS attributes_json
                ORDER BY n.id
                """
            )
            edge_records = session.run(
                """
                MATCH (a:StoryNode)-[r:RELATES]->(b:StoryNode)
                RETURN a.id AS source, b.id AS target, r.edge_type AS type, r.attributes_json AS attributes_json
                ORDER BY a.id, b.id, r.edge_type
                """
            )
            chapter_records = session.run(
                """
                MATCH (c)
                WHERE 'ChapterRecord' IN labels(c)
                RETURN properties(c) AS props
                ORDER BY c.chapter_number
                """
            )
            project_props = project_record["props"]

            return StoryGraph(
                project={
                    "title": project_props["title"],
                    "theme": project_props["theme"],
                    "style_guide": json.loads(project_props.get("style_guide_json", "{}")),
                },
                nodes=[
                    Node(
                        id=record["id"],
                        type=record["type"],
                        name=record["name"],
                        attributes=json.loads(record["attributes_json"] or "{}"),
                    )
                    for record in node_records
                ],
                edges=[
                    Edge(
                        source=record["source"],
                        target=record["target"],
                        type=record["type"],
                        attributes=json.loads(record["attributes_json"] or "{}"),
                    )
                    for record in edge_records
                ],
                chapter_history=[
                    ChapterRecord(
                        chapter_number=record["props"]["chapter_number"],
                        title=record["props"]["title"],
                        summary=record["props"]["summary"],
                        focus_characters=json.loads(record["props"].get("focus_characters_json", "[]")),
                        location=record["props"]["location"],
                        motif=record["props"]["motif"],
                        event_id=record["props"]["event_id"],
                    )
                    for record in chapter_records
                ],
            )

    def save(self, graph: StoryGraph) -> None:
        with self.driver.session(database=self.database) as session:
            session.execute_write(self._save_graph, graph)

    @staticmethod
    def _save_graph(tx, graph: StoryGraph) -> None:
        tx.run("MATCH (n) DETACH DELETE n")
        tx.run(
            """
            CREATE (p:ProjectMeta {
              id: 'project',
              title: $title,
              theme: $theme,
              style_guide_json: $style_guide_json
            })
            """,
            title=graph.project["title"],
            theme=graph.project["theme"],
            style_guide_json=json.dumps(graph.project.get("style_guide", {}), ensure_ascii=False),
        )

        tx.run(
            """
            UNWIND $nodes AS item
            CREATE (:StoryNode {
              id: item.id,
              type: item.type,
              name: item.name,
              attributes_json: item.attributes_json
            })
            """,
            nodes=[
                {
                    "id": node.id,
                    "type": node.type,
                    "name": node.name,
                    "attributes_json": json.dumps(node.attributes, ensure_ascii=False),
                }
                for node in graph.nodes
            ],
        )

        tx.run(
            """
            UNWIND $edges AS item
            MATCH (a:StoryNode {id: item.source})
            MATCH (b:StoryNode {id: item.target})
            CREATE (a)-[:RELATES {
              edge_type: item.type,
              attributes_json: item.attributes_json
            }]->(b)
            """,
            edges=[
                {
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.type,
                    "attributes_json": json.dumps(edge.attributes, ensure_ascii=False),
                }
                for edge in graph.edges
            ],
        )

        tx.run(
            """
            UNWIND $chapters AS item
            CREATE (:ChapterRecord {
              chapter_number: item.chapter_number,
              title: item.title,
              summary: item.summary,
              focus_characters_json: item.focus_characters_json,
              location: item.location,
              motif: item.motif,
              event_id: item.event_id
            })
            """,
            chapters=[
                {
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.title,
                    "summary": chapter.summary,
                    "focus_characters_json": json.dumps(chapter.focus_characters, ensure_ascii=False),
                    "location": chapter.location,
                    "motif": chapter.motif,
                    "event_id": chapter.event_id,
                }
                for chapter in graph.chapter_history
            ],
        )
