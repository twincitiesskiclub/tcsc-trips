"""Probe Slack admin analytics API for per-user activity data.

Usage:
    source env/bin/activate
    python scripts/probe_slack_activity.py

Reads SLACK_ADMIN_TOKEN, SLACK_YOUR_COOKIE, SLACK_YOUR_X_ID from .env.

The endpoint we're verifying is admin.analytics.getMemberAnalytics — found by
inspecting network requests on https://app.slack.com/manage/T02J2AVLSCT/analytics.
This returns aggregated activity counts over a date range (7d/30d/90d).
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()


WORKSPACE_DOMAIN = "twincitiesskiclub"
BASE_URL = f"https://{WORKSPACE_DOMAIN}.slack.com/api/"
TEAM_ID = "T02J2AVLSCT"


def get_creds():
    token = os.environ.get("SLACK_ADMIN_TOKEN")
    cookie = os.environ.get("SLACK_YOUR_COOKIE")
    x_id = os.environ.get("SLACK_YOUR_X_ID")
    missing = [n for n, v in [
        ("SLACK_ADMIN_TOKEN", token),
        ("SLACK_YOUR_COOKIE", cookie),
        ("SLACK_YOUR_X_ID", x_id),
    ] if not v]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        sys.exit(2)
    return token, cookie, x_id


def fmt_ts(ts):
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return f"(unparseable: {ts!r})"


def call_analytics(api_method, data, cookie, x_id):
    """Call an admin.analytics.* endpoint. Uses _x_app_name=manage."""
    url = BASE_URL + api_method
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Origin": "https://app.slack.com",
        "Cookie": cookie,
    }
    params = {
        "_x_id": x_id,
        "slack_route": TEAM_ID,
        "_x_version_ts": "noversion",
        "_x_frontend_build_type": "current",
        "_x_gantry": "true",
        "fp": "12",
        "_x_num_retries": "0",
    }
    # Common analytics params
    full_data = {
        **data,
        "_x_mode": "online",
        "_x_app_name": "manage",
    }
    files = {key: (None, str(value)) for key, value in full_data.items()}
    response = requests.post(url, headers=headers, params=params, files=files, timeout=30)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, {"_raw": response.text[:500]}


def probe_member_analytics(token, cookie, x_id, extra_params, label):
    print(f"\n{'=' * 70}")
    print(f"PROBE: admin.analytics.getMemberAnalytics — {label}")
    print(f"  extra params: {extra_params}")
    print(f"{'=' * 70}")

    status, body = call_analytics(
        "admin.analytics.getMemberAnalytics",
        {
            "token": token,
            "count": "10",
            "sort_column": "real_name",
            "sort_direction": "asc",
            "query": "",
            "_x_reason": "loadMembersDataForTimeRange",
            **extra_params,
        },
        cookie, x_id,
    )

    print(f"HTTP {status}")
    print(f"top-level keys: {list(body.keys())}")
    print(f"  num_found: {body.get('num_found')}")

    if not body.get("ok"):
        print(f"  → not ok: {body.get('error', '?')}")
        if "_raw" in body:
            print(f"  raw: {body['_raw'][:300]}")
        return None

    # Response key is member_activity (verified)
    members = body.get("member_activity") or []
    print(f"  member_activity rows: {len(members)}")

    if members:
        sample = members[0]
        print(f"\n  first-member keys: {sorted(sample.keys())}")
        print(f"\n  full first-member object:")
        print(json.dumps(sample, indent=2, default=str))

        print(f"\n  activity-relevant fields across first 5 members:")
        for m in members[:5]:
            uid = m.get("user_id") or m.get("id") or "?"
            name = m.get("real_name") or m.get("name") or "?"
            activity_hints = {k: v for k, v in m.items() if any(
                tok in k.lower() for tok in ("active", "last", "seen", "post", "message", "day", "count")
            )}
            print(f"    {uid} ({name}):")
            for k, v in activity_hints.items():
                print(f"      {k} = {v!r}")

    next_cursor = body.get("next_cursor_mark", "")
    print(f"\n  next_cursor_mark: {next_cursor!r}")

    return body


def probe_available_ranges(token, cookie, x_id):
    print(f"\n{'=' * 70}")
    print("PROBE: admin.analytics.getAvailableDateRange (type=member)")
    print(f"{'=' * 70}")

    status, body = call_analytics(
        "admin.analytics.getAvailableDateRange",
        {
            "token": token,
            "type": "member",
            "_x_reason": "fetchMembersDataAvailableDateRange",
        },
        cookie, x_id,
    )
    print(f"HTTP {status}")
    print(f"response: {json.dumps(body, indent=2, default=str)}")
    return body if body.get("ok") else None


def main():
    token, cookie, x_id = get_creds()
    print(f"Using token starting {token[:10]}...")

    # Step 1: get the available date range (end_date may lag today by 1+ days)
    ranges = probe_available_ranges(token, cookie, x_id)
    if not ranges or not ranges.get("ok"):
        print("Could not fetch available date range — aborting.")
        sys.exit(1)
    start_date = ranges["start_date"]
    end_date = ranges["end_date"]
    print(f"\nUsing window {start_date} → {end_date} (max available)")

    # Step 2: full-population pull, sorted by date_last_active desc.
    # Paginate via next_cursor_mark to confirm we can get every member.
    print(f"\n{'=' * 70}")
    print("FULL PULL: every member, sorted by date_last_active desc")
    print(f"{'=' * 70}")

    all_members = []
    cursor = ""
    page = 0
    while True:
        page += 1
        params = {
            "token": token,
            "start_date": start_date,
            "end_date": end_date,
            "count": "500",
            "sort_column": "date_last_active",
            "sort_direction": "desc",
            "query": "",
            "_x_reason": "loadMembersDataForTimeRange",
        }
        if cursor:
            params["cursor_mark"] = cursor

        status, body = call_analytics("admin.analytics.getMemberAnalytics", params, cookie, x_id)
        if not body.get("ok"):
            print(f"  page {page} failed: {body.get('error')}")
            break

        rows = body.get("member_activity") or []
        all_members.extend(rows)
        num_found = body.get("num_found", "?")
        next_cursor = body.get("next_cursor_mark", "")
        print(f"  page {page}: {len(rows)} rows (running total {len(all_members)} / {num_found})")

        if not next_cursor or next_cursor == cursor or len(rows) == 0:
            break
        if len(all_members) >= (num_found or 0):
            break
        cursor = next_cursor

    print(f"\nFetched {len(all_members)} total members.")

    if all_members:
        # Distribution of date_last_active relative to today
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        now = _dt.now(tz=_tz.utc)
        buckets = {"0_30": 0, "30_90": 0, "90_180": 0, "180_365": 0, "over_365": 0, "never": 0}
        for m in all_members:
            ts = m.get("date_last_active") or 0
            if ts <= 0:
                buckets["never"] += 1
                continue
            age_days = (now - _dt.fromtimestamp(ts, tz=_tz.utc)).days
            if age_days < 30:
                buckets["0_30"] += 1
            elif age_days < 90:
                buckets["30_90"] += 1
            elif age_days < 180:
                buckets["90_180"] += 1
            elif age_days < 365:
                buckets["180_365"] += 1
            else:
                buckets["over_365"] += 1
        print("\nDistribution of date_last_active (days ago):")
        for k, v in buckets.items():
            print(f"  {k:10s}: {v}")

        # Show most/least recent
        sorted_members = sorted(
            (m for m in all_members if m.get("date_last_active", 0) > 0),
            key=lambda m: m["date_last_active"],
            reverse=True,
        )
        print("\nTop 3 most recently active:")
        for m in sorted_members[:3]:
            print(f"  {m['user_id']} {m.get('real_name'):<30} {fmt_ts(m['date_last_active'])}")
        print("\nBottom 3 (oldest activity, excluding 'never'):")
        for m in sorted_members[-3:]:
            print(f"  {m['user_id']} {m.get('real_name'):<30} {fmt_ts(m['date_last_active'])}")

        # Billable-seat distribution (bonus)
        billable = sum(1 for m in all_members if m.get("is_billable_seat"))
        print(f"\nBillable seats: {billable} / {len(all_members)}")

    print("\n" + "=" * 70)
    print("DONE — review member object fields above.")
    print("We need a field that lets us decide 'active in last 90 days' per user.")
    print("=" * 70)


if __name__ == "__main__":
    main()
