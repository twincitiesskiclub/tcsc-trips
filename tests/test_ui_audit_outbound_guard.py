import socket
import pytest

import scripts.ui_audit.outbound_guard as outbound_guard_module
from scripts.ui_audit.outbound_guard import OutboundBlocked, install_outbound_guard


@pytest.fixture(autouse=True, scope="module")
def guard():
    """Install the guard for this module only, then fully undo it.

    install_outbound_guard() patches process-wide state (socket.socket.connect
    / connect_ex, slack_sdk's WebClient.api_call, smtplib's SMTP(_SSL).__init__)
    and never reverts it on its own -- that's intentional for the real UI audit
    harness, which is a short-lived, single-purpose process. But this test file
    runs inside the shared pytest process for the whole suite, so without a
    teardown here, every test file that happens to run afterward would inherit
    a blocked smtplib/Slack client for reasons that have nothing to do with its
    own code. Save the five patched attributes, install, yield, then restore
    them and reset _INSTALLED so the module is left exactly as it was found.
    """
    import smtplib
    from slack_sdk.web.client import WebClient

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_api_call = WebClient.api_call
    original_smtp_init = smtplib.SMTP.__init__
    original_smtp_ssl_init = smtplib.SMTP_SSL.__init__

    install_outbound_guard()
    yield

    socket.socket.connect = original_connect
    socket.socket.connect_ex = original_connect_ex
    WebClient.api_call = original_api_call
    smtplib.SMTP.__init__ = original_smtp_init
    smtplib.SMTP_SSL.__init__ = original_smtp_ssl_init
    # A later install() in this same process would otherwise no-op forever,
    # since install_outbound_guard() only ever checks this module-level flag.
    outbound_guard_module._INSTALLED = False


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


@pytest.mark.skipif(
    not hasattr(socket, "AF_UNIX"), reason="AF_UNIX not available on this platform"
)
def test_af_unix_socket_is_not_blocked_as_outbound(tmp_path):
    """AF_UNIX addresses are plain str/bytes paths, not (host, port) tuples.

    A unix-domain socket can never leave the machine, so it must never be
    treated as an outbound connection -- even though it doesn't look like the
    (host, port) tuples the loopback check was written around.
    """
    socket_path = str(tmp_path / "ui-audit-guard-test.sock")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(1)

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(socket_path)  # must not raise OutboundBlocked
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
