"""Attendance analytics: Slack archive, session lineage, dashboards."""

CHANNELS = {
    "C042G463AQ1": "announcements-practices",
    "C03FKTTHNHW": "announcements-summer",     # archived; import needs the user token
    "C047BRZH1LG": "extra-training-fun",       # archived raw only, never sessions
    "C0B2VN1LU11": "announcements-general",
    "C02HXN45214": "announcements-adventures", # archived 2026-05-11, imported once
    "C068ECRE0PQ": "tech-trip-signups",
    "C02J1FDSBHT": "chat",
    "C046XRWC4NR": "races-information",
}
# Template and app-era practice parsing.
SESSION_CHANNELS = ("C042G463AQ1", "C03FKTTHNHW")
# Sessions only through `create` corrections (the event catalog).
EVENT_CHANNELS = ("C0B2VN1LU11", "C02HXN45214", "C02J1FDSBHT", "C046XRWC4NR")
# Slack Workflow trip sign-ups, parsed by parse_trips.
TRIP_CHANNEL = "C068ECRE0PQ"
CANDIDATE_CHANNELS = SESSION_CHANNELS + EVENT_CHANNELS
# Reaction-only candidates are limited to announcement channels.
REACTION_CANDIDATE_CHANNELS = ("C042G463AQ1", "C03FKTTHNHW", "C0B2VN1LU11", "C02HXN45214")
LINEAGE_CHANNELS = CANDIDATE_CHANNELS + (TRIP_CHANNEL,)
SYNC_CHANNELS = ("C042G463AQ1", "C047BRZH1LG", "C0B2VN1LU11", "C068ECRE0PQ", "C02J1FDSBHT", "C046XRWC4NR")
CATEGORIES = ("practice", "kickoff", "social", "board", "race", "volunteer", "banquet", "other", "trip")
