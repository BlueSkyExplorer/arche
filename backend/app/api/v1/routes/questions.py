from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.deps import get_current_user, get_db
from app.schemas.question import QuestionCreate, QuestionPatch, QuestionRead
from app.services import questions

router = APIRouter(prefix="/questions", tags=["questions"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]


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
