from fastapi import APIRouter

from app.api.v1.routes import (
    answer_sheet_exports,
    assets,
    exam_imports,
    exports,
    health,
    papers,
    questions,
    templates,
    workspaces,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(workspaces.router)
router.include_router(questions.router)
router.include_router(templates.router)
router.include_router(papers.router)
router.include_router(assets.router)
router.include_router(exports.router)
router.include_router(exam_imports.router)
router.include_router(answer_sheet_exports.router)
