from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.deps import get_current_user, get_db
from app.schemas.domain import (
    PaperCreate,
    PaperDetail,
    PaperPatch,
    PaperQuestionPut,
    PaperQuestionRead,
    PaperRead,
    PaperSectionDetail,
    PaperSectionRead,
    SectionCreate,
    SectionPatch,
)
from app.services import papers
from app.services.numbering import (
    NumberingConfig,
    QuestionForNumbering,
    SectionForNumbering,
    number_questions,
)

router = APIRouter(prefix="/papers", tags=["papers"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]


def detail(db: Session, paper: object) -> PaperDetail:
    tree, total = papers.paper_tree(db, paper)  # type: ignore[arg-type]
    base = PaperRead.model_validate(paper).model_dump()
    template = papers.get_template_for_paper(db, paper)  # type: ignore[arg-type]
    style = template.numbering_config_json.get("question_style", "1.")
    numbered = number_questions(
        [
            SectionForNumbering(
                position=section.position,
                questions=[
                    QuestionForNumbering(
                        question_id=pq.id,
                        position=pq.position,
                        marks=question.marks,
                        marks_override=pq.marks_override,
                    )
                    for pq, question in pairs
                ],
            )
            for section, pairs in tree
        ],
        NumberingConfig(question_style=style),
    )
    labels = {item.question.question_id: item.label for item in numbered}
    sections = [
        PaperSectionDetail(
            **PaperSectionRead.model_validate(section).model_dump(),
            questions=[
                PaperQuestionRead.model_validate(pq).model_copy(update={"label": labels[pq.id]})
                for pq, _ in pairs
            ],
        )
        for section, pairs in tree
    ]
    return PaperDetail(**base, sections=sections, total_marks=total)


@router.get("", response_model=list[PaperRead])
def paper_list(current_user: User, db: Db) -> list[PaperRead]:
    return [PaperRead.model_validate(x) for x in papers.list_papers(db, current_user)]


@router.post("", response_model=PaperRead, status_code=201)
def paper_create(data: PaperCreate, current_user: User, db: Db) -> PaperRead:
    return PaperRead.model_validate(papers.create_paper(db, current_user, data))


@router.get("/{paper_id}", response_model=PaperDetail)
def paper_get(paper_id: UUID, current_user: User, db: Db) -> PaperDetail:
    return detail(db, papers.get_paper(db, paper_id, current_user))


@router.patch("/{paper_id}", response_model=PaperRead)
def paper_patch(paper_id: UUID, data: PaperPatch, current_user: User, db: Db) -> PaperRead:
    return PaperRead.model_validate(papers.patch_paper(db, paper_id, current_user, data))


@router.post("/{paper_id}/sections", response_model=PaperSectionRead, status_code=201)
def section_create(
    paper_id: UUID, data: SectionCreate, current_user: User, db: Db
) -> PaperSectionRead:
    return PaperSectionRead.model_validate(papers.create_section(db, paper_id, current_user, data))


@router.patch("/{paper_id}/sections/{section_id}", response_model=PaperSectionRead)
def section_patch(
    paper_id: UUID, section_id: UUID, data: SectionPatch, current_user: User, db: Db
) -> PaperSectionRead:
    return PaperSectionRead.model_validate(
        papers.patch_section(db, paper_id, section_id, current_user, data)
    )


@router.delete("/{paper_id}/sections/{section_id}", status_code=204)
def section_delete(paper_id: UUID, section_id: UUID, current_user: User, db: Db) -> Response:
    papers.delete_section(db, paper_id, section_id, current_user)
    return Response(status_code=204)


@router.put("/{paper_id}/sections/{section_id}/questions", response_model=list[PaperQuestionRead])
def questions_put(
    paper_id: UUID, section_id: UUID, data: list[PaperQuestionPut], current_user: User, db: Db
) -> list[PaperQuestionRead]:
    return [
        PaperQuestionRead.model_validate(x)
        for x in papers.replace_questions(db, paper_id, section_id, current_user, data)
    ]
