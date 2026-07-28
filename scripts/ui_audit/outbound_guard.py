"""Hard block on outbound network traffic for the UI audit server.

The admin UI has buttons that send Slack messages to the whole club and capture
Stripe payments. The screenshot harness must never be able to fire one, so this
blocks at the socket layer -- below every HTTP client -- rather than trying to
enumerate the libraries that might reach outward.

Loopback stays open because the app server and PostgreSQL are both local.
"""

import ipaddress
import socket

_INSTALLED = False


class OutboundBlocked(RuntimeError):
    """Raised when code under the UI audit harness attempts to reach the network."""


def _is_loopback(address) -> bool:
    """True when the connect target is on this machine."""
    if isinstance(address, (str, bytes)):
        # AF_UNIX socket paths (or an abstract-namespace name). A unix-domain
        # socket can never leave the machine, so it's inherently loopback.
        return True
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if host in ("localhost", "", None):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # A hostname that is not a bare IP literal. Do not resolve it -- resolving
        # is itself a network call, and any non-loopback name is blocked anyway.
        return False


def install_outbound_guard() -> None:
    """Patch sockets, Slack, and SMTP so outbound traffic raises immediately.

    Idempotent: calling more than once will not double-wrap the socket methods.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(self, address, *args, **kwargs):
        if not _is_loopback(address):
            raise OutboundBlocked(
                f"UI audit harness blocked an outbound connection to {address!r}"
            )
        return real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):
        if not _is_loopback(address):
            raise OutboundBlocked(
                f"UI audit harness blocked an outbound connection to {address!r}"
            )
        return real_connect_ex(self, address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex

    # Named errors for the two clients that would do member-visible damage.
    try:
        from slack_sdk.web.client import WebClient

        def blocked_slack(*args, **kwargs):
            raise OutboundBlocked(
                "UI audit harness blocked a Slack API call. No message was sent."
            )

        WebClient.api_call = blocked_slack
    except ImportError:
        pass

    import smtplib

    def blocked_smtp(*args, **kwargs):
        raise OutboundBlocked("UI audit harness blocked an SMTP connection.")

    smtplib.SMTP.__init__ = blocked_smtp
    smtplib.SMTP_SSL.__init__ = blocked_smtp
