from unittest.mock import patch, MagicMock

import pytest

from app.verify import providers
from app.verify.providers import ProviderError


def _resp(status=200, body=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = body or {}
    return m


@pytest.fixture(autouse=True)
def app_ctx():
    from app import create_app
    app = create_app()
    app.config.update(
        TESTING=True,
        TWILIO_ACCOUNT_SID="AC_test", TWILIO_API_KEY_SID="SK_test",
        TWILIO_API_KEY_SECRET="secret", TWILIO_VERIFY_SERVICE_SID="VA_test",
        TWILIO_MESSAGING_SERVICE_SID="MG_test", RESEND_API_KEY="re_test",
    )
    with app.app_context():
        yield


@patch("app.verify.providers.requests.post")
def test_verify_start_posts_to_verify_api(mock_post):
    mock_post.return_value = _resp(201, {"status": "pending"})
    providers.twilio_verify_start("+16128677165")
    url = mock_post.call_args.args[0]
    assert "verify.twilio.com" in url and "/Verifications" in url
    assert mock_post.call_args.kwargs["data"] == {
        "To": "+16128677165", "Channel": "sms"}


@patch("app.verify.providers.requests.post")
def test_verify_check_true_only_on_approved(mock_post):
    mock_post.return_value = _resp(200, {"status": "approved"})
    assert providers.twilio_verify_check("+16128677165", "123456") is True
    mock_post.return_value = _resp(200, {"status": "pending"})
    assert providers.twilio_verify_check("+16128677165", "000000") is False


@patch("app.verify.providers.requests.post")
def test_verify_start_raises_provider_error_with_code(mock_post):
    mock_post.return_value = _resp(429, {"code": 60203, "message": "Max send attempts reached"})
    with pytest.raises(ProviderError) as exc:
        providers.twilio_verify_start("+16128677165")
    assert exc.value.code == 60203


@patch("app.verify.providers.requests.post")
def test_send_sms_surfaces_opt_out_code(mock_post):
    mock_post.return_value = _resp(400, {"code": 21610, "message": "unsubscribed"})
    with pytest.raises(ProviderError) as exc:
        providers.twilio_send_sms("+16128677165", "hi")
    assert exc.value.code == 21610


@patch("app.verify.providers.requests.post")
def test_resend_send_code_uses_club_sender(mock_post):
    mock_post.return_value = _resp(200, {"id": "abc"})
    providers.resend_send_code("rob@example.com", "Rob", "482913")
    payload = mock_post.call_args.kwargs["json"]
    assert payload["from"] == "Twin Cities Ski Club <club@tcsc.ski>"
    assert payload["subject"] == "Your TCSC code: 482913"
    assert "482913" in payload["text"]
