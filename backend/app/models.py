from datetime import datetime, date
from sqlalchemy import String, Text, DateTime, Date, Float, ForeignKey, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    meetings = relationship('Meeting', back_populates='user', cascade='all, delete-orphan')

class Meeting(Base):
    __tablename__ = 'meetings'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(240))
    meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    project: Mapped[str | None] = mapped_column(String(160), nullable=True)
    participants: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='uploaded')
    summary: Mapped[str] = mapped_column(Text, default='')
    transcript: Mapped[str] = mapped_column(Text, default='')
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_mode: Mapped[str] = mapped_column(String(30), default='mock')
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship('User', back_populates='meetings')
    tasks = relationship('Task', back_populates='meeting', cascade='all, delete-orphan')
    decisions = relationship('Decision', back_populates='meeting', cascade='all, delete-orphan')
    risks = relationship('Risk', back_populates='meeting', cascade='all, delete-orphan')

class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    meeting_id: Mapped[int | None] = mapped_column(ForeignKey('meetings.id'), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default='')
    owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default='medium')
    status: Mapped[str] = mapped_column(String(30), default='needs_review')
    evidence: Mapped[str] = mapped_column(Text, default='')
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meeting = relationship('Meeting', back_populates='tasks')

class Decision(Base):
    __tablename__ = 'decisions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey('meetings.id'))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default='')
    evidence: Mapped[str] = mapped_column(Text, default='')
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    meeting = relationship('Meeting', back_populates='decisions')

class Risk(Base):
    __tablename__ = 'risks'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey('meetings.id'))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default='medium')
    suggested_resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(30), default='open')
    note: Mapped[str] = mapped_column(Text, default='')
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    meeting = relationship('Meeting', back_populates='risks')
