"""Tests for the reactivation custom step handler validation logic."""

from unittest.mock import patch, MagicMock

import pytest


class FakeSlackUser:
    def __init__(self, slack_uid):
        self.slack_uid = slack_uid
        self.id = 1


class FakeUser:
    def __init__(self, status='ALUMNI', seasons_since_active=2, email='test@example.com',
                 first_name='Jane', last_name='Doe', slack_user=None):
        self.status = status
        self.seasons_since_active = seasons_since_active
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.slack_user = slack_user

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


def validate_reactivation(user):
    """Replicate validation logic from the handler for unit testing."""
    if not user:
        return False, "No linked account found"
    if user.status != 'ALUMNI' or user.seasons_since_active < 2:
        return False, "Not eligible for reactivation"
    return True, None


class TestReactivationValidation:

    def test_valid_alumni_2_seasons(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=2)
        valid, error = validate_reactivation(user)
        assert valid is True
        assert error is None

    def test_valid_alumni_3_seasons(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=3)
        valid, error = validate_reactivation(user)
        assert valid is True

    def test_rejects_active_user(self):
        user = FakeUser(status='ACTIVE', seasons_since_active=0)
        valid, error = validate_reactivation(user)
        assert valid is False
        assert 'Not eligible' in error

    def test_rejects_1_season_alumni(self):
        user = FakeUser(status='ALUMNI', seasons_since_active=1)
        valid, error = validate_reactivation(user)
        assert valid is False

    def test_rejects_none_user(self):
        valid, error = validate_reactivation(None)
        assert valid is False
        assert 'No linked account' in error

    def test_rejects_pending_user(self):
        user = FakeUser(status='PENDING', seasons_since_active=0)
        valid, error = validate_reactivation(user)
        assert valid is False
