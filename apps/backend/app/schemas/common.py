from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime


class MessageResponse(BaseModel):
    message: str

