from __future__ import annotations

from typing import Protocol

from .schema import StoryGraph


class GraphBackend(Protocol):
    def exists(self) -> bool:
        ...

    def load(self) -> StoryGraph:
        ...

    def save(self, graph: StoryGraph) -> None:
        ...
