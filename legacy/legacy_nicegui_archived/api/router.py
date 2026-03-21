"""Top-level `/api/v1` router composition."""

from __future__ import annotations

from fastapi import APIRouter

from legacy.legacy_nicegui_archived.api.routes import admin, auth, results, tasks

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(tasks.router)
api_v1_router.include_router(results.router)
