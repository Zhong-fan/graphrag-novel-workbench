from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api_routes import register_routes
from .api_support import _ensure_seed_novels, create_run_index_job, mount_spa
from .config import load_settings
from .db import db_session, init_db


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="鏅ㄦ祦鍐欎綔鍙?",
        version="1.0.0",
        description="ChenFlow Workbench锛氬熀浜?GraphRAG + MySQL + Neo4j + Vue 鐨勪腑鏂囧皬璇村垱浣滃伐浣滃彴銆?",
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
        with db_session() as db:
            _ensure_seed_novels(db)

    router = APIRouter()
    run_index_job = create_run_index_job(settings)
    register_routes(router, settings=settings, run_index_job=run_index_job)
    app.include_router(router)
    mount_spa(app, settings)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
