from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests
from sqlalchemy.orm import scoped_session, sessionmaker

from app.analytics import weather
from app.analytics.models import PracticeSession, WeatherHour
from app.analytics.weather import fetch_hours, session_weather, to_inches
from app.integrations.daylight import get_daylight_info
from app.models import db
from app.utils import CENTRAL_TZ
from tests.analytics.conftest import load_fixture


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def sample_get(*args, **kwargs):
    return Resp(200, load_fixture("openmeteo_sample.json"))


def test_units_read_from_response():
    calls = []

    def http_get(url, **kwargs):
        calls.append((url, kwargs))
        return sample_get()

    hours = fetch_hours(44.98, -93.32, date(2099, 12, 20), date(2099, 12, 20), http_get=http_get)
    assert len(hours) == 26
    h = {x["hour_local"]: x for x in hours}[datetime(2099, 12, 20, 18)]
    assert h["temp_f"] == pytest.approx(-2.7)
    assert h["snow_depth_in"] == pytest.approx(0.689 * 12)
    assert h["weather_code"] == 71
    assert all(h["hour_local"].tzinfo is None for h in hours)
    assert calls[0][0] == "https://archive-api.open-meteo.com/v1/archive"
    assert calls[0][1]["params"] == {
        "latitude": 44.98, "longitude": -93.32,
        "start_date": "2099-12-20", "end_date": "2099-12-20",
        "hourly": "temperature_2m,apparent_temperature,precipitation,snowfall,snow_depth,wind_speed_10m,weather_code",
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
        "precipitation_unit": "inch", "timezone": "America/Chicago",
    }
    assert 0 < calls[0][1]["timeout"] <= 60


@pytest.mark.parametrize("resp", [Resp(500, {}), Resp(200, ValueError("bad json")), Resp(200, {"error": True})])
def test_fetch_failure_writes_nothing(resp, caplog):
    assert fetch_hours(1, 2, date(2099, 1, 1), date(2099, 1, 1), http_get=lambda *a, **k: resp) == []
    assert caplog.records


@pytest.mark.parametrize("variable", weather.HOURLY_VARS)
def test_unknown_units_fail_entire_response(variable, caplog):
    body = load_fixture("openmeteo_sample.json")
    body["hourly_units"][variable] = "unknown"
    assert fetch_hours(1, 2, date(2099, 1, 1), date(2099, 1, 1),
                       http_get=lambda *a, **k: Resp(200, body)) == []
    assert caplog.records


@pytest.mark.parametrize("damage", ["short_array", "no_units", "invalid_time"])
def test_malformed_response_returns_no_partial_hours(damage):
    body = load_fixture("openmeteo_sample.json")
    if damage == "short_array":
        body["hourly"]["snow_depth"].pop()
    elif damage == "no_units":
        del body["hourly_units"]
    else:
        body["hourly"]["time"][-1] = "invalid"
    assert fetch_hours(1, 2, date(2099, 1, 1), date(2099, 1, 1),
                       http_get=lambda *a, **k: Resp(200, body)) == []


def test_timeout_returns_no_hours(caplog):
    def timeout(*args, **kwargs):
        raise requests.Timeout("test timeout")
    assert fetch_hours(1, 2, date(2099, 1, 1), date(2099, 1, 1), http_get=timeout) == []
    assert caplog.records


def test_to_inches():
    assert to_inches(25.4, "mm") == pytest.approx(1)
    assert to_inches(2.54, "cm") == pytest.approx(1)
    assert to_inches(0.0254, "m") == pytest.approx(1)
    assert to_inches(1, "inch") == 1
    assert to_inches(None, "mm") is None
    with pytest.raises(ValueError):
        to_inches(1, "unknown")


def test_to_inches_feet():
    assert to_inches(0.689, "ft") == pytest.approx(0.689 * 12)


def test_metric_response_and_null_values():
    body = load_fixture("openmeteo_sample.json")
    body["hourly_units"].update(precipitation="mm", snowfall="cm")
    body["hourly"]["precipitation"][20] = 25.4
    body["hourly"]["snowfall"][20] = 2.54
    body["hourly"]["snow_depth"][20] = None
    hours = fetch_hours(1, 2, date(2099, 12, 20), date(2099, 12, 20),
                        http_get=lambda *a, **k: Resp(200, body))
    assert hours[20]["precip_in"] == pytest.approx(1)
    assert hours[20]["snowfall_in"] == pytest.approx(1)
    assert hours[20]["snow_depth_in"] is None


def test_session_window_math():
    hours = {x["hour_local"]: SimpleNamespace(**x) for x in fetch_hours(
        0, 0, date(2099, 12, 20), date(2099, 12, 20), http_get=sample_get)}
    w = session_weather(datetime(2099, 12, 20, 18, 15), hours)
    assert w["temp_f"] == pytest.approx(-2.7)
    assert w["feels_like_f"] == 0 and w["wind_mph"] == 0
    assert w["precip_in"] == pytest.approx(0.05)
    assert w["snowfall_in"] == pytest.approx(0.2)
    assert w["snowfall_prior_24h_in"] == pytest.approx(0.1)
    assert w["snow_depth_in"] == pytest.approx(0.689 * 12)
    assert w["weather_code"] == 71


def test_prior_window_boundaries_and_missing_data():
    start = datetime(2099, 12, 20, 23, 45)
    hour = start.replace(minute=0)
    hours = {hour + timedelta(hours=offset): SimpleNamespace(snowfall_in=value, precip_in=value)
             for offset, value in [(-25, 100), (-24, 1), (-1, 2), (0, 4), (1, 8), (2, 100)]}
    w = session_weather(start, hours)
    assert w["snowfall_prior_24h_in"] == 3
    assert w["snowfall_in"] == 12 and w["precip_in"] == 12
    assert all(value is None for value in session_weather(start, {}).values())


def make_session(key, **kwargs):
    values = dict(session_key=f"weather-test:{key}", group_key=f"weather-test:{key}",
                  era="template", date=date(2099, 12, 20), start_time=time(18, 15),
                  day_of_week="Sunday", season_label="2099-2100", lat=44.984, lon=-93.324)
    values.update(kwargs)
    return PracticeSession(**values)


@pytest.mark.parametrize("month", [7, 12])
@pytest.mark.parametrize("aware", [False, True])
def test_apply_weather_cache_only_and_signed_daylight(db_session, monkeypatch, month, aware):
    def no_network(*args, **kwargs):
        pytest.fail("weather application must never call the network")
    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    day = date(2099, month, 20)
    start = datetime.combine(day, time(18, 15))
    sunset = CENTRAL_TZ.localize(datetime.combine(day, time(19)))
    if not aware:
        sunset = sunset.astimezone(timezone.utc).replace(tzinfo=None)
    monkeypatch.setattr(weather, "get_daylight_info", lambda *args: SimpleNamespace(sunset=sunset))
    row = make_session("cached", date=day)
    later = make_session("uncached", date=day, start_time=time(20))
    missing = make_session("unknown", lat=None)
    db_session.add(WeatherHour(lat=44.98, lon=-93.32, hour_local=start.replace(minute=0), temp_f=-2.7))
    assert weather.apply_weather([row, later, missing]) == 1
    assert row.temp_f == -2.7 and row.minutes_after_sunset == -45
    assert later.temp_f is None and later.minutes_after_sunset == 60
    assert missing.minutes_after_sunset is None


def test_apply_uses_real_daylight_helper(db_session):
    row = make_session("daylight")
    start = CENTRAL_TZ.localize(datetime.combine(row.date, row.start_time))
    sunset = get_daylight_info(row.lat, row.lon, start).sunset
    if sunset.tzinfo is None:
        sunset = sunset.replace(tzinfo=timezone.utc)
    assert weather.apply_weather([row]) == 0
    assert row.minutes_after_sunset == int((start - sunset).total_seconds() / 60)


@pytest.fixture
def committing_session(app, monkeypatch):
    # Production commits execute within a test-owned transaction, never leaking rows.
    with app.app_context(), db.engine.connect() as connection:
        transaction = connection.begin()
        session = scoped_session(sessionmaker(bind=connection, join_transaction_mode="create_savepoint"))
        monkeypatch.setattr(db, "session", session)
        try:
            # Isolate candidates from other workers' fixtures, under rollback.
            session.query(PracticeSession).delete(synchronize_session=False)
            session.query(WeatherHour).delete(synchronize_session=False)
            yield session
        finally:
            session.remove()
            transaction.rollback()


def test_fetch_missing_groups_cutoff_upsert_and_commit(committing_session):
    rows = [make_session("first"), make_session("same-rounded", lat=44.981, lon=-93.321),
            make_session("earlier", date=date(2099, 12, 19), start_time=time(23)),
            make_session("other-location", lat=45.12),
            make_session("too-recent", date=date(2099, 12, 21)),
            make_session("unknown", lon=None), make_session("no-time", start_time=None),
            make_session("already-cached", lat=46.12)]
    committing_session.add_all(rows)
    old = WeatherHour(lat=44.98, lon=-93.32, hour_local=datetime(2099, 12, 20, 17), snowfall_in=99)
    committing_session.add_all([old, WeatherHour(lat=46.12, lon=-93.32,
        hour_local=datetime(2099, 12, 20, 18), temp_f=99)])
    calls = []
    def http_get(url, **kwargs):
        calls.append(kwargs["params"])
        return sample_get()
    stats = weather.fetch_missing_weather(today=date(2099, 12, 26), http_get=http_get)
    assert stats == {"locations": 2, "hours": 52, "sessions": 4, "errors": 0}
    by_lat = {call["latitude"]: call for call in calls}
    assert by_lat[44.98]["start_date"] == "2099-12-18"
    assert by_lat[45.12]["start_date"] == "2099-12-19"
    assert all(call["end_date"] == "2099-12-20" for call in calls)
    assert all(call["longitude"] == -93.32 for call in calls)
    committing_session.expire_all()
    assert old.snowfall_in == pytest.approx(0.1)
    assert old.fetched_at is not None and old.fetched_at.tzinfo is None
    assert WeatherHour.query.count() == 53
    assert rows[0].temp_f == pytest.approx(-2.7)
    assert rows[0].snowfall_prior_24h_in == pytest.approx(0.1)
    assert rows[4].temp_f is None and rows[7].temp_f is None
    assert weather.fetch_missing_weather(today=date(2099, 12, 26), http_get=http_get) == {
        "locations": 0, "hours": 0, "sessions": 0, "errors": 0}
    assert len(calls) == 2


def test_fetch_failure_count_and_retry(committing_session, monkeypatch):
    row = make_session("retry")
    committing_session.add(row)
    monkeypatch.setattr(weather, "today_central", lambda: date(2099, 12, 26))
    stats = weather.fetch_missing_weather(http_get=lambda *a, **k: Resp(503, {}))
    assert stats == {"locations": 1, "hours": 0, "sessions": 0, "errors": 1}
    assert WeatherHour.query.count() == 0 and row.temp_f is None
    stats = weather.fetch_missing_weather(http_get=sample_get)
    assert stats == {"locations": 1, "hours": 26, "sessions": 1, "errors": 0}
    assert row.temp_f == pytest.approx(-2.7)


def test_rebuild_fills_real_cached_weather_without_network(db_session, monkeypatch):
    from app.analytics.rebuild import rebuild
    from app.analytics.history_config import load_history_config

    def no_network(*args, **kwargs):
        pytest.fail("rebuild must never call the network")
    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    # Reuse real lineage inputs through a synthetic app practice and configured venue.
    from app.practices.models import Practice, PracticeLocation
    location = PracticeLocation(name="Weather test venue", latitude=44.984, longitude=-93.324)
    practice = Practice(date=datetime(2099, 12, 20, 18, 15), day_of_week="Sunday", location=location,
                        slack_channel_id="CFAKEWEATHER", slack_message_ts="4101400000.000010")
    db_session.add(practice)
    db_session.add(WeatherHour(lat=44.98, lon=-93.32, hour_local=datetime(2099, 12, 20, 18), temp_f=-2.7))
    db_session.flush()
    rebuild(cfg=load_history_config(), commit=False)
    row = PracticeSession.query.filter_by(practice_id=practice.id).one()
    assert row.temp_f == pytest.approx(-2.7)
    assert row.minutes_after_sunset is not None


@pytest.mark.parametrize("observed_field", [None, *weather.HOURLY_VARS])
def test_archive_lag_null_hours_remain_missing_and_retry(committing_session, observed_field):
    row = make_session("archive-lag")
    committing_session.add(row)
    body = load_fixture("openmeteo_sample.json")
    for variable in weather.HOURLY_VARS:
        body["hourly"][variable] = [None] * len(body["hourly"]["time"])
    start_index = body["hourly"]["time"].index("2099-12-20T18:00")
    if observed_field:
        body["hourly"][observed_field][start_index] = 0
    stats = weather.fetch_missing_weather(today=date(2099, 12, 26),
                                         http_get=lambda *a, **k: Resp(200, body))
    assert stats["hours"] == (1 if observed_field else 0)
    assert WeatherHour.query.count() == (1 if observed_field else 0)
    stats = weather.fetch_missing_weather(today=date(2099, 12, 26), http_get=sample_get)
    if observed_field:
        assert stats["locations"] == 0
    else:
        assert stats["hours"] == 26 and stats["sessions"] == 1
        assert row.temp_f == pytest.approx(-2.7)
