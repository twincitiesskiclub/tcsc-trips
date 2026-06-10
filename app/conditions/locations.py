"""Four Twin Cities Nordic locations exposed by the conditions API."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    lat: float
    lon: float
    skinnyski_slug: str  # for trail_conditions lookup


LOCATIONS: list[Location] = [
    Location('wirth', 'Theodore Wirth', 44.9956, -93.3252, 'theodore-wirth'),
    Location('hyland', 'Hyland Park', 44.8451, -93.3950, 'hyland-park'),
    Location('french', 'French Park', 44.9787, -93.4854, 'french-park'),
    Location('battlecreek', 'Battle Creek', 44.9351, -93.0290, 'battle-creek'),
]
