from __future__ import annotations

from fastapi import APIRouter

from .api_routes_auth import register_auth_routes
from .api_routes_generation import register_generation_routes
from .api_routes_longform import register_longform_routes
from .api_routes_novels import register_novel_routes
from .api_routes_projects import register_project_routes
from .config import Settings


def register_routes(
    router: APIRouter,
    *,
    settings: Settings,
) -> None:
    register_auth_routes(router, settings=settings)
    register_project_routes(router)
    register_novel_routes(router, settings=settings)
    register_generation_routes(router, settings=settings)
    register_longform_routes(router, settings=settings)
