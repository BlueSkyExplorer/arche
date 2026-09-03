from fastapi import APIRouter

from app.api.v1.routes import health, questions, templates, workspaces

router = APIRouter()
router.include_router(health.router)
router.include_router(workspaces.router)
router.include_router(questions.router)
router.include_router(templates.router)
