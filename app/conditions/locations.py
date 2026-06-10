"""Four Twin Cities Nordic locations exposed by the conditions API."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    lat: float
    lon: float
    skinnyski_name: str  # canonical venue name for trail_conditions fuzzy lookup


LOCATIONS: list[Location] = [
    Location('wirth', 'Theodore Wirth', 44.9956, -93.3252, 'Theodore Wirth Park'),
    Location('hyland', 'Hyland Park', 44.8451, -93.3950, 'Hyland Lake Park Reserve'),
    Location('french', 'French Park', 44.9787, -93.4854, 'French Regional Park'),
    Location('battlecreek', 'Battle Creek', 44.9351, -93.0290, 'Battle Creek Regional Park'),
]
