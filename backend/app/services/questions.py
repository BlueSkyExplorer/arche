from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.models.question import Question
from app.services.authorization import assert_workspace_access


def get_question(db: Session, question_id: UUID, current_user: CurrentUser) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    assert_workspace_access(question.workspace_id, current_user.workspace_id)
    return question
