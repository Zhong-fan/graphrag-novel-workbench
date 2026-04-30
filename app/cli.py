from __future__ import annotations

import argparse
import json

from .config import load_settings
from .runtime import build_pipeline
from .schema import ChapterRequest


def command_init() -> None:
    settings = load_settings()
    pipeline = build_pipeline(settings)
    pipeline.initialize_state()
    target = settings.neo4j_uri if settings.graph_backend == "neo4j" else settings.state_path
    print(f"已初始化图后端：{settings.graph_backend} -> {target}")


def command_generate_chapter(args: argparse.Namespace) -> None:
    pipeline = build_pipeline()
    pipeline.initialize_state()
    request = ChapterRequest(
        chapter_number=args.chapter_number,
        premise=args.premise,
        focus_characters=args.focus_characters,
        location=args.location,
        motif=args.motif,
    )
    draft = pipeline.generate_chapter(request)
    settings = load_settings()
    output_path = settings.output_dir / f"chapter_{args.chapter_number:02d}.md"
    print(f"已生成章节文件：{output_path}")
    print(draft.title)
    print(draft.summary)


def command_show_graph() -> None:
    settings = load_settings()
    store = build_pipeline(settings).graph_store
    if not store.exists():
        raise RuntimeError("状态文件不存在，请先运行 `python -m app.cli init`。")
    graph = store.load()
    payload = {
        "graph_backend": settings.graph_backend,
        "project": graph.project,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "chapter_count": len(graph.chapter_history),
        "last_chapters": [record.__dict__ for record in graph.chapter_history[-3:]],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GraphRAG 轻小说 MVP 命令行工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="从种子世界初始化状态")

    generate = subparsers.add_parser("generate-chapter", help="生成章节草稿")
    generate.add_argument("--chapter-number", type=int, required=True)
    generate.add_argument("--focus-characters", nargs="+", required=True)
    generate.add_argument("--location", required=True)
    generate.add_argument("--motif", required=True)
    generate.add_argument("--premise", required=True)

    subparsers.add_parser("show-graph", help="查看当前图状态摘要")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        command_init()
    elif args.command == "generate-chapter":
        command_generate_chapter(args)
    elif args.command == "show-graph":
        command_show_graph()
    else:
        raise RuntimeError(f"不支持的命令：{args.command}")


if __name__ == "__main__":
    main()
