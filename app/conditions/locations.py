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
    Location('wirth', 'Theo', 44.9956, -93.3252, 'Theodore Wirth Park'),
    Location('elm', 'Elm', 45.1809, -93.4307, 'Elm Creek Park Reserve'),
    Location('hyland', 'Hyland', 44.8451, -93.3950, 'Hyland Lake Park Reserve'),
    # Telemark (the old Telemark Lodge trailhead outside Cable, WI, on the
    # Birkie Trail). Its trail report doubles as the input to the Birkie
    # fever status, hence the 'Birkie Trail' SkinnySkI venue name.
    Location('telemark', 'Telemark', 46.2046, -91.2553, 'Birkie Trail'),
]
