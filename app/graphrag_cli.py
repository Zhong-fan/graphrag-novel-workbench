from __future__ import annotations

from .graphrag_local_embeddings import enable_local_embedding_fallback


def main() -> None:
    enable_local_embedding_fallback()

    from graphrag.cli.main import app as graphrag_app

    graphrag_app(prog_name="graphrag")


if __name__ == "__main__":
    main()
