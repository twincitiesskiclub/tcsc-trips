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
    Location('wirth', 'Theo Wirth', 44.9956, -93.3252, 'Theodore Wirth Park'),
    Location('elm', 'Elm Creek', 45.1809, -93.4307, 'Elm Creek Park Reserve'),
    Location('hyland', 'Hyland Nordic', 44.8451, -93.3950, 'Hyland Lake Park Reserve'),
    # The OO trailhead on the Birkie Trail (County Hwy OO west of Seeley, WI).
    # Its trail report doubles as the input to the Birkie likelihood status.
    Location('oo', 'Double OO', 46.0645, -91.2460, 'Birkie Trail'),
]
