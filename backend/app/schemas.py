from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, EmailStr

class Register(BaseModel): name: str = Field(min_length=1,max_length=100); email: EmailStr; password: str = Field(min_length=8,max_length=128)
class Login(BaseModel): email: EmailStr; password: str
class TaskInput(BaseModel):
    title: str = Field(min_length=1,max_length=300); description: str=''; owner: str|None=None; due_date: date|None=None
    priority: Literal['low','medium','high','critical']='medium'; status: Literal['needs_review','pending','in_progress','completed','blocked']='pending'; evidence: str=''; meeting_id: int|None=None
class TaskPatch(BaseModel):
    title: str|None=None; description: str|None=None; owner: str|None=None; due_date: date|None=None
    priority: Literal['low','medium','high','critical']|None=None
    status: Literal['needs_review','pending','in_progress','completed','blocked']|None=None
    evidence: str|None=None
class MeetingPatch(BaseModel): title: str|None=None; project: str|None=None; participants: str|None=None; meeting_date: date|None=None
class DecisionPatch(BaseModel): title: str|None=None; description: str|None=None
class RiskPatch(BaseModel): status: Literal['open','in_progress','resolved','accepted']|None=None; note: str|None=None; severity: Literal['low','medium','high','critical']|None=None
class KeyPoint(BaseModel): text: str; evidence: str=''
class ExtractedDecision(BaseModel): title: str; description: str=''; evidence: str=''; confidence: float=Field(default=0.5,ge=0,le=1)
class ExtractedTask(BaseModel):
    title: str; description: str=''; owner: str|None=None; due_date: date|None=None
    priority: Literal['low','medium','high','critical']='medium'; evidence: str=''; confidence: float=Field(default=0.5,ge=0,le=1)
class ExtractedRisk(BaseModel):
    description: str; severity: Literal['low','medium','high','critical']='medium'; suggested_resolution: str|None=None
    evidence: str=''; confidence: float=Field(default=0.5,ge=0,le=1)
class OpenQuestion(BaseModel): question: str; evidence: str=''
class Extraction(BaseModel):
    summary: str
    key_points: list[KeyPoint] = []
    decisions: list[ExtractedDecision] = []
    action_items: list[ExtractedTask] = []
    risks_and_blockers: list[ExtractedRisk] = []
    open_questions: list[OpenQuestion] = []
