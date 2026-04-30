from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JsonDict = dict[str, Any]


@dataclass
class Node:
    id: str
    type: str
    name: str
    attributes: JsonDict = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    type: str
    attributes: JsonDict = field(default_factory=dict)


@dataclass
class ChapterRecord:
    chapter_number: int
    title: str
    summary: str
    focus_characters: list[str]
    location: str
    motif: str
    event_id: str


@dataclass
class StoryGraph:
    project: JsonDict
    nodes: list[Node]
    edges: list[Edge]
    chapter_history: list[ChapterRecord]


@dataclass
class RetrievalResult:
    focus_nodes: list[Node]
    related_nodes: list[Node]
    related_edges: list[Edge]
    recent_chapters: list[ChapterRecord]


@dataclass
class ChapterRequest:
    chapter_number: int
    premise: str
    focus_characters: list[str]
    location: str
    motif: str


@dataclass
class SceneBeat:
    label: str
    focus: str
    tension: str
    turn: str


@dataclass
class ChapterPlan:
    chapter_goal: str
    emotional_shift: str
    motif_image: str
    scene_beats: list[SceneBeat] = field(default_factory=list)
    continuity_notes: list[str] = field(default_factory=list)


@dataclass
class ExtractedEdge:
    source: str
    target: str
    type: str
    attributes: JsonDict = field(default_factory=dict)


@dataclass
class ChapterUpdate:
    event_name: str
    event_summary: str
    event_attributes: JsonDict = field(default_factory=dict)
    continuity_notes: list[str] = field(default_factory=list)
    edges: list[ExtractedEdge] = field(default_factory=list)


@dataclass
class ChapterDraft:
    title: str
    summary: str
    content: str
