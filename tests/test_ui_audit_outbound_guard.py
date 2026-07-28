import socket
import pytest

from scripts.ui_audit.outbound_guard import OutboundBlocked, install_outbound_guard


@pytest.fixture(autouse=True)
def guard():
    install_outbound_guard()


def test_external_connection_is_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(OutboundBlocked):
        s.connect(("slack.com", 443))


def test_external_connect_ex_is_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(OutboundBlocked):
        s.connect_ex(("api.stripe.com", 443))


def test_loopback_is_allowed():
    """The database and the app server itself must still be reachable."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))  # must not raise
    client.close()
    server.close()


def test_slack_client_raises_named_error():
    from slack_sdk import WebClient

    with pytest.raises(OutboundBlocked) as exc:
        WebClient(token="xoxb-fake").auth_test()
    assert "Slack" in str(exc.value)


def test_smtplib_is_blocked():
    import smtplib

    with pytest.raises(OutboundBlocked):
        smtplib.SMTP("smtp.gmail.com", 587)


def test_install_is_idempotent():
    """A second install() must not re-wrap the already-patched socket methods.

    A buggy guard that skips the _INSTALLED check would read the already-guarded
    method as "real_connect" and close over it again on every extra call. That
    doesn't blow up after just one redundant call, so this checks two things a
    trivial "loopback still works" assertion would miss: the patched methods
    keep their original identity across repeated installs, and many redundant
    installs in a row don't build a call chain deep enough to misbehave.
    """
    connect_after_first_install = socket.socket.connect
    connect_ex_after_first_install = socket.socket.connect_ex

    install_outbound_guard()
    install_outbound_guard()

    assert socket.socket.connect is connect_after_first_install, (
        "second install() call rewrapped socket.socket.connect"
    )
    assert socket.socket.connect_ex is connect_ex_after_first_install, (
        "second install() call rewrapped socket.socket.connect_ex"
    )

    # Pile on more redundant installs -- a chain-of-wrappers bug would still
    # "work" after two calls but risks recursion depth issues after many.
    for _ in range(50):
        install_outbound_guard()

    assert socket.socket.connect is connect_after_first_install, (
        "repeated install() calls rewrapped socket.socket.connect"
    )

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))  # must not raise
    client.close()
    server.close()
