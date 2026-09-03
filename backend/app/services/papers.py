from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.models import Paper, PaperQuestion, PaperSection, Question, TemplateProfile
from app.schemas.domain import (
    PaperCreate,
    PaperPatch,
    PaperQuestionPut,
    SectionCreate,
    SectionPatch,
)
from app.services.authorization import assert_workspace_access


def get_paper(db: Session, paper_id: UUID, user: CurrentUser) -> Paper:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404, "Paper not found")
    assert_workspace_access(paper.workspace_id, user.workspace_id)
    return paper


def get_template_for_paper(db: Session, paper: Paper) -> TemplateProfile:
    template = db.get(TemplateProfile, paper.template_profile_id)
    if template is None or template.workspace_id != paper.workspace_id:
        raise HTTPException(404, "Template not found")
    return template


def get_section(db: Session, paper_id: UUID, section_id: UUID, user: CurrentUser) -> PaperSection:
    get_paper(db, paper_id, user)
    section = db.get(PaperSection, section_id)
    if section is None or section.paper_id != paper_id or section.workspace_id != user.workspace_id:
        raise HTTPException(404, "Section not found")
    return section


def list_papers(db: Session, user: CurrentUser) -> list[Paper]:
    return list(
        db.scalars(
            select(Paper)
            .where(Paper.workspace_id == user.workspace_id)
            .order_by(Paper.created_at.desc())
        )
    )


def _template(db: Session, template_id: UUID, user: CurrentUser) -> None:
    item = db.get(TemplateProfile, template_id)
    if item is None or item.workspace_id != user.workspace_id:
        raise HTTPException(404, "Template not found")


def create_paper(db: Session, user: CurrentUser, data: PaperCreate) -> Paper:
    _template(db, data.template_profile_id, user)
    paper = Paper(workspace_id=user.workspace_id, **data.model_dump(mode="json"))
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


def patch_paper(db: Session, paper_id: UUID, user: CurrentUser, data: PaperPatch) -> Paper:
    paper = get_paper(db, paper_id, user)
    changes = data.model_dump(exclude_unset=True, mode="json")
    if "template_profile_id" in changes:
        _template(db, data.template_profile_id, user)  # type: ignore[arg-type]
    for key, value in changes.items():
        setattr(paper, key, value)
    db.commit()
    db.refresh(paper)
    return paper


def create_section(
    db: Session, paper_id: UUID, user: CurrentUser, data: SectionCreate
) -> PaperSection:
    paper = get_paper(db, paper_id, user)
    section = PaperSection(
        workspace_id=user.workspace_id, paper_id=paper.id, **data.model_dump(mode="json")
    )
    db.add(section)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Section position already exists") from None
    db.refresh(section)
    return section


def patch_section(
    db: Session, paper_id: UUID, section_id: UUID, user: CurrentUser, data: SectionPatch
) -> PaperSection:
    section = get_section(db, paper_id, section_id, user)
    for key, value in data.model_dump(exclude_unset=True, mode="json").items():
        setattr(section, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Section position already exists") from None
    db.refresh(section)
    return section


def delete_section(db: Session, paper_id: UUID, section_id: UUID, user: CurrentUser) -> None:
    db.delete(get_section(db, paper_id, section_id, user))
    db.commit()


def replace_questions(
    db: Session, paper_id: UUID, section_id: UUID, user: CurrentUser, items: list[PaperQuestionPut]
) -> list[PaperQuestion]:
    section = get_section(db, paper_id, section_id, user)
    if len({item.question_id for item in items}) != len(items):
        raise HTTPException(422, "Duplicate question_id")
    questions = (
        list(
            db.scalars(
                select(Question).where(
                    Question.id.in_([x.question_id for x in items]),
                    Question.workspace_id == user.workspace_id,
                )
            )
        )
        if items
        else []
    )
    if len(questions) != len(items):
        raise HTTPException(404, "Question not found")
    db.execute(delete(PaperQuestion).where(PaperQuestion.paper_section_id == section.id))
    db.flush()
    rows = [
        PaperQuestion(
            workspace_id=user.workspace_id,
            paper_section_id=section.id,
            question_id=item.question_id,
            position=index,
            marks_override=item.marks_override,
            settings_json={},
        )
        for index, item in enumerate(items)
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def paper_tree(
    db: Session, paper: Paper
) -> tuple[list[tuple[PaperSection, list[tuple[PaperQuestion, Question]]]], Decimal]:
    sections = list(
        db.scalars(
            select(PaperSection)
            .where(PaperSection.paper_id == paper.id)
            .order_by(PaperSection.position)
        )
    )
    tree = []
    total = Decimal(0)
    for section in sections:
        pairs = list(
            db.execute(
                select(PaperQuestion, Question)
                .join(Question)
                .where(PaperQuestion.paper_section_id == section.id)
                .order_by(PaperQuestion.position)
            ).tuples()
        )
        for pq, question in pairs:
            total += pq.marks_override if pq.marks_override is not None else question.marks
        tree.append((section, pairs))
    return tree, total
