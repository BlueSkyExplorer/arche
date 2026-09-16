from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db
from app.core.storage import LocalDirStorage
from app.schemas.question import (
    QuestionCreate,
    QuestionIngestDraft,
    QuestionPatch,
    QuestionRead,
)
from app.services import questions
from app.services.assets import create_asset_from_bytes
from app.services.doc_convert import convert_doc_to_docx
from app.services.question_ingest import (
    _ingest_with_images,
    attach_image_assets,
    ingest_question_text,
)
from app.services.uploads import validate_document_upload

router = APIRouter(prefix="/questions", tags=["questions"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post("/ingest", response_model=list[QuestionIngestDraft])
async def question_ingest(
    current_user: User,
    db: Db,
    settings: SettingsDep,
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> list[QuestionIngestDraft]:
    """Parse a pasted question set (``text``) or an uploaded ``.doc/.docx`` into
    reviewable Draft questions. Nothing is persisted — teachers review the
    drafts, then save accepted ones via POST /questions."""
    if (text is None) == (file is None):
        raise HTTPException(status_code=422, detail="Provide exactly one of: text, file")
    if file is not None:
        filename = (file.filename or "").lower()
        data = await file.read()
        ext = validate_document_upload(filename, len(data))
        if ext == ".doc":
            data = convert_doc_to_docx(data, settings)
        try:
            from io import BytesIO

            from docx import Document

            doc = Document(BytesIO(data))
            drafts, attachments = _ingest_with_images(data, doc)
            if attachments:
                storage = LocalDirStorage(settings.storage_local_dir)
                asset_ids = [
                    create_asset_from_bytes(
                        db, current_user, storage, "question_image", a["image"], "embedded"
                    ).id
                    for a in attachments
                ]
                attach_image_assets(drafts, attachments, asset_ids)
            return drafts
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    return ingest_question_text(text)


@router.get("", response_model=list[QuestionRead])
def question_list(
    current_user: User,
    db: Db,
    subject: str | None = None,
    level: str | None = None,
    status: str | None = None,
    q: str | None = Query(default=None),
) -> list[QuestionRead]:
    return [
        QuestionRead.model_validate(x)
        for x in questions.list_questions(db, current_user, subject, level, status, q)
    ]


@router.post("", response_model=QuestionRead, status_code=201)
def question_create(data: QuestionCreate, current_user: User, db: Db) -> QuestionRead:
    return QuestionRead.model_validate(questions.create_question(db, current_user, data))


@router.get("/{question_id}", response_model=QuestionRead)
def question_detail(question_id: UUID, current_user: User, db: Db) -> QuestionRead:
    return QuestionRead.model_validate(questions.get_question(db, question_id, current_user))


@router.patch("/{question_id}", response_model=QuestionRead)
def question_patch(
    question_id: UUID, data: QuestionPatch, current_user: User, db: Db
) -> QuestionRead:
    return QuestionRead.model_validate(
        questions.patch_question(db, question_id, current_user, data)
    )


@router.delete("/{question_id}", status_code=204)
def question_delete(question_id: UUID, current_user: User, db: Db) -> Response:
    questions.delete_question(db, question_id, current_user)
    return Response(status_code=204)