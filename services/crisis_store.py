"""In-memory crisis event store."""
import secrets
import time

from models import CrisisEvent, CrisisEventCreate, CrisisEventPatch

_store: dict[str, CrisisEvent] = {}


def add(data: CrisisEventCreate) -> CrisisEvent:
    event_id = secrets.token_hex(4)
    event = CrisisEvent(id=event_id, created_at=time.time(), **data.model_dump())
    _store[event_id] = event
    return event


def get(event_id: str) -> CrisisEvent | None:
    return _store.get(event_id)


def list_all(type_filter: str | None = None, status_filter: str | None = None) -> list[CrisisEvent]:
    result = list(_store.values())
    if type_filter:
        result = [e for e in result if e.type == type_filter]
    if status_filter:
        result = [e for e in result if e.status == status_filter]
    return result


def patch(event_id: str, data: CrisisEventPatch) -> CrisisEvent | None:
    event = _store.get(event_id)
    if not event:
        return None
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    updated = event.model_copy(update=updates)
    _store[event_id] = updated
    return updated


def delete(event_id: str) -> bool:
    if event_id in _store:
        del _store[event_id]
        return True
    return False


def list_active() -> list[CrisisEvent]:
    return [e for e in _store.values() if e.status == "active"]
