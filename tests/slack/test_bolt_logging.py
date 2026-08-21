"""The Bolt base logger must emit INFO to stdout.

Gunicorn configures no root handlers and leaves the root logger at WARNING,
and slack_bolt copies the base logger's settings onto every listener logger
it creates. Without an explicit INFO base logger, the event-receipt
instrumentation (the "slack event received" middleware and the link_shared
lines) is silently dropped in production.
"""

import logging


def test_bolt_base_logger_enables_info_with_stream_handler():
    from app.slack.bolt_app import _build_bolt_base_logger

    base = _build_bolt_base_logger()
    assert base.isEnabledFor(logging.INFO)
    assert any(isinstance(h, logging.StreamHandler) for h in base.handlers)


def test_bolt_base_logger_does_not_stack_handlers():
    from app.slack.bolt_app import _build_bolt_base_logger

    first = _build_bolt_base_logger()
    second = _build_bolt_base_logger()
    assert second is first
    assert len(second.handlers) == 1


def test_listener_logger_inherits_info_from_base():
    from slack_bolt.logger import get_bolt_app_logger

    from app.slack.bolt_app import _build_bolt_base_logger

    class FakeListener:
        pass

    listener_logger = get_bolt_app_logger(
        "test-bolt-logging", FakeListener, _build_bolt_base_logger()
    )
    assert listener_logger.isEnabledFor(logging.INFO)
    assert any(
        isinstance(h, logging.StreamHandler) for h in listener_logger.handlers
    )
