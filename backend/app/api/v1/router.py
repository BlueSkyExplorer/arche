from fastapi import APIRouter

from app.api.v1.routes import assets, exports, health, papers, questions, templates, workspaces

router = APIRouter()
router.include_router(health.router)
router.include_router(workspaces.router)
router.include_router(questions.router)
router.include_router(templates.router)
router.include_router(papers.router)
router.include_router(assets.router)
router.include_router(exports.router)
