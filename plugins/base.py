from abc import ABC, abstractmethod
from datetime import datetime


class BasePlugin(ABC):
    layer_id: str
    layer_name: str
    data_type: str  # e.g. "air_quality", "resources", "events", "threat_zone"

    _last_updated: datetime | None = None

    @abstractmethod
    async def fetch(self) -> dict:
        """Return a GeoJSON FeatureCollection."""
        ...

    @property
    def last_updated(self) -> datetime | None:
        return self._last_updated
