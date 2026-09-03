from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import String, cast, delete, or_, select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.models import Paper, PaperQuestion, PaperSection, Question
from app.schemas.question import QuestionCreate, QuestionPatch
from app.services.authorization import assert_workspace_access


def get_question(db: Session, question_id: UUID, user: CurrentUser) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(404, "Question not found")
    assert_workspace_access(question.workspace_id, user.workspace_id)
    return question


def list_questions(
    db: Session,
    user: CurrentUser,
    subject: str | None = None,
    level: str | None = None,
    question_status: str | None = None,
    q: str | None = None,
) -> list[Question]:
    stmt = select(Question).where(Question.workspace_id == user.workspace_id)
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if level:
        stmt = stmt.where(Question.level == level)
    if question_status:
        stmt = stmt.where(Question.status == question_status)
    if q:
        term = f"%{q}%"
        stmt = stmt.where(
            or_(Question.internal_title.ilike(term), cast(Question.tags_json, String).ilike(term))
        )
    return list(db.scalars(stmt.order_by(Question.created_at.desc())))


def create_question(db: Session, user: CurrentUser, data: QuestionCreate) -> Question:
    question = Question(workspace_id=user.workspace_id, **data.model_dump(mode="json"))
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def patch_question(
    db: Session, question_id: UUID, user: CurrentUser, data: QuestionPatch
) -> Question:
    question = get_question(db, question_id, user)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, question_id: UUID, user: CurrentUser) -> None:
    """Hard-delete; active-paper references conflict, archived-paper links are removed."""
    question = get_question(db, question_id, user)
    reference = db.scalar(
        select(PaperQuestion.id)
        .join(PaperSection)
        .join(Paper)
        .where(PaperQuestion.question_id == question.id, Paper.status != "archived")
    )
    if reference is not None:
        raise HTTPException(409, "Question is used by a non-archived paper")
    archived_links = select(PaperQuestion.id).join(PaperSection).join(Paper).where(
        PaperQuestion.question_id == question.id,
        Paper.status == "archived",
    )
    db.execute(delete(PaperQuestion).where(PaperQuestion.id.in_(archived_links)))
    db.delete(question)
    db.commit()
