from __future__ import annotations

import argparse

from .api import main as run_api
from .config import load_settings


def command_health() -> None:
    settings = load_settings()
    print("service=ChenFlow Workbench")
    print(f"writer_model={settings.writer_model}")
    print(f"utility_model={settings.utility_model}")
    print(f"embedding_model={settings.embedding_model}")
    print(f"mysql={settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChenFlow Workbench 命令行工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("serve", help="启动 FastAPI 服务")
    subparsers.add_parser("health", help="输出当前工作台基础配置")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        run_api()
    elif args.command == "health":
        command_health()
    else:
        raise RuntimeError(f"不支持的命令：{args.command}")


if __name__ == "__main__":
    main()
