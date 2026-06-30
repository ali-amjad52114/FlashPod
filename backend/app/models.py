from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# ---------------------------------------------------------------------------
# SQLAlchemy ORM models
# ---------------------------------------------------------------------------


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    drawings: Mapped[list["Drawing"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    templates: Mapped[list["Template"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    takeoffs: Mapped[list["Takeoff"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Drawing(Base):
    __tablename__ = "drawings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    filepath: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="image/png"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="drawings")


# DEPRECATED — worker no longer needs template crops; detect symbols internally.
# Kept to avoid a migration; remove once frontend SymbolsScreen is updated.
class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True
    )
    sym_type: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    filepath: Mapped[str] = mapped_column(String(1024), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="templates")


class Takeoff(Base):
    __tablename__ = "takeoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True
    )
    drawing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drawings.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )  # pending | running | done | error
    detections: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    priced_items: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    proposal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_size: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="takeoffs")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ProjectOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DrawingOut(BaseModel):
    id: int
    project_id: int
    filename: str
    url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateOut(BaseModel):
    id: int
    project_id: int
    sym_type: str
    label: str
    threshold: float
    created_at: datetime

    model_config = {"from_attributes": True}


class TakeoffRequest(BaseModel):
    drawing_id: int


class TakeoffOut(BaseModel):
    id: int
    project_id: int
    drawing_id: int
    status: str
    detections: Optional[list] = None
    priced_items: Optional[list] = None
    proposal: Optional[str] = None
    image_size: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ItemCorrection(BaseModel):
    quantity: Optional[int] = Field(None, ge=0)
    unit_price: Optional[float] = Field(None, ge=0)
