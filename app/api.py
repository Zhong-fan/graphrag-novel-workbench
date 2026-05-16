from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api_routes import register_routes
from .api_support import mount_spa
from .batch_generation_worker import start_batch_generation_worker, stop_batch_generation_worker
from .config import load_settings
from .db import init_db


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="ChenFlow Workbench",
        version="1.0.0",
        description="面向创作者的中文小说生成与整理工作台。",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        start_batch_generation_worker(settings)

    @app.on_event("shutdown")
    def shutdown() -> None:
        stop_batch_generation_worker()

    router = APIRouter()
    register_routes(router, settings=settings)
    app.include_router(router)
    mount_spa(app, settings)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
