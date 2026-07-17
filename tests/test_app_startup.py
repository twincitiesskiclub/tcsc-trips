from unittest.mock import Mock

import app as app_module


def _prepare_factory(monkeypatch):
    monkeypatch.setattr(app_module, "load_stripe_config", lambda: None)
    monkeypatch.setenv("FLASK_SECRET_KEY", "startup-test-secret")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://tcsc:tcsc@localhost:5432/tcsc_trips",
    )


def test_create_app_never_calls_create_all(monkeypatch):
    _prepare_factory(monkeypatch)
    monkeypatch.delenv("TCSC_MIGRATION_ONLY", raising=False)
    create_all = Mock(side_effect=AssertionError("schema mutation"))
    scheduler = Mock(return_value=False)
    monkeypatch.setattr(app_module.db, "create_all", create_all)
    monkeypatch.setattr(app_module, "init_scheduler", scheduler)

    application = app_module.create_app()

    create_all.assert_not_called()
    scheduler.assert_called_once_with(application)


def test_create_app_starts_scheduler_for_non_migration_only_value(monkeypatch):
    _prepare_factory(monkeypatch)
    monkeypatch.setenv("TCSC_MIGRATION_ONLY", "0")
    create_all = Mock(side_effect=AssertionError("schema mutation"))
    scheduler = Mock(return_value=False)
    monkeypatch.setattr(app_module.db, "create_all", create_all)
    monkeypatch.setattr(app_module, "init_scheduler", scheduler)

    application = app_module.create_app()

    create_all.assert_not_called()
    scheduler.assert_called_once_with(application)


def test_create_app_skips_scheduler_in_migration_only_mode(monkeypatch):
    _prepare_factory(monkeypatch)
    monkeypatch.setenv("TCSC_MIGRATION_ONLY", "1")
    create_all = Mock(side_effect=AssertionError("schema mutation"))
    scheduler = Mock(return_value=False)
    monkeypatch.setattr(app_module.db, "create_all", create_all)
    monkeypatch.setattr(app_module, "init_scheduler", scheduler)

    application = app_module.create_app()

    assert "migrate" in application.extensions
    create_all.assert_not_called()
    scheduler.assert_not_called()
