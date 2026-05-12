"""Pydantic data models for project state and intermediate artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SectionStatus(str, Enum):
    pending = "pending"
    writing = "writing"
    done = "done"
    reviewed = "reviewed"


class WorkflowStage(str, Enum):
    init = "INIT"
    ask = "ASK_QUESTIONS"
    brief = "MAKE_BRIEF"
    plan = "MAKE_PLAN"
    toc = "MAKE_TOC"
    style = "MAKE_STYLE_GUIDE_AND_GLOSSARY"
    outlines = "MAKE_CHAPTER_OUTLINES"
    write = "WRITE_SECTIONS"
    assemble = "ASSEMBLE_BOOK"
    done = "DONE"


class SectionState(BaseModel):
    section_id: str          # e.g. "sec01_02"
    title: str
    status: SectionStatus = SectionStatus.pending


class ChapterState(BaseModel):
    chapter_id: str          # e.g. "ch01"
    title: str
    outline_done: bool = False
    sections: dict[str, SectionState] = Field(default_factory=dict)


class ProjectState(BaseModel):
    slug: str
    title: str
    info: str = ""
    stage: WorkflowStage = WorkflowStage.init
    completed_stages: list[str] = Field(default_factory=list)
    chapters: dict[str, ChapterState] = Field(default_factory=dict)

    def mark_stage_done(self, stage: WorkflowStage) -> None:
        if stage.value not in self.completed_stages:
            self.completed_stages.append(stage.value)
        self.stage = stage

    def is_stage_done(self, stage: WorkflowStage) -> bool:
        return stage.value in self.completed_stages


class TOCEntry(BaseModel):
    chapter_num: int
    title: str
    sections: list[str] = Field(default_factory=list)


class SectionInfo(BaseModel):
    chapter_num: int
    chapter_title: str
    section_num: int
    section_title: str
    description: str = ""


class ReviewResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    suggestion: str = ""
    revised_content: Optional[str] = None
