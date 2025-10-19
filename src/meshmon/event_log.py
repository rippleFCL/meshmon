import datetime
import enum

import pydantic
import structlog


class EventType(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


LEVEL_MAP = {
    EventType.INFO: 20,
    EventType.WARNING: 30,
    EventType.ERROR: 40,
}


class EventID(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    mid: str
    src: str
    network_id: str | None = None
    uid: str | None = None


class Event(pydantic.BaseModel):
    event_type: EventType
    message: str
    title: str
    date: datetime.datetime


class EventLog:
    def __init__(self):
        self.events: dict[EventID, Event] = {}
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.event_log", component="EventLog"
        )

    def log_event(self, event_type: EventType, mid: EventID, message: str, title: str):
        event = Event(
            event_type=event_type,
            message=message,
            title=title,
            date=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        self.events[mid] = event
        self.logger.log(
            LEVEL_MAP.get(event_type, 20),
            "Logged event",
            event_type=event_type.value,
            mid=mid,
            message=message,
            title=title,
        )

    def clear_event(
        self,
        mid: str | None = None,
        src: str | None = None,
        network_id: str | None = None,
        uid: str | None = None,
    ):
        if mid is None and src is None and network_id is None and uid is None:
            self.events.clear()
            self.logger.info("Cleared all events")
            return
        to_delete: list[EventID] = []
        for eid in self.events.keys():
            if mid is not None and eid.mid != mid:
                continue
            if src is not None and eid.src != src:
                continue
            if network_id is not None and eid.network_id != network_id:
                continue
            if uid is not None and eid.uid != uid:
                continue
            to_delete.append(eid)
        for eid in to_delete:
            del self.events[eid]
            data = {
                "mid": eid.mid,
                "src": eid.src,
                "network_id": eid.network_id,
                "uid": eid.uid,
            }
            non_none_data = {k: v for k, v in data.items() if v is not None}
            self.logger.info("Cleared event", **non_none_data)
