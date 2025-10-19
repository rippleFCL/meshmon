import datetime
from enum import Enum

from pydantic import BaseModel


class ApiEventType(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ApiEvent(BaseModel):
    event_type: ApiEventType
    message: str
    title: str
    date: datetime.datetime


class EventApi(BaseModel):
    events: list[ApiEvent] = []
