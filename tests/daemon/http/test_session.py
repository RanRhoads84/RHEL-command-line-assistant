from unittest.mock import MagicMock, patch

import pytest

from command_line_assistant.constants import VERSION
from command_line_assistant.daemon.http.session import get_session
from command_line_assistant.config.schemas.backend import AuthSchema


def test_session_headers(mock_config):
    """Test that session headers are properly set"""
    session = get_session(mock_config)

    assert session.headers["User-Agent"] == f"clad/{VERSION}"
    assert session.headers["Content-Type"] == "application/json"


@patch("command_line_assistant.daemon.http.session.Session")
def test_session_creation(mock_session, mock_config):
    """Test basic session creation"""
    mock_session_instance = MagicMock()
    mock_session.return_value = mock_session_instance

    session = get_session(mock_config)

    mock_session.assert_called_once()
    assert session == mock_session_instance


def test_different_endpoint_configuration(mock_config):
    """Test session creation with different endpoint configurations"""
    custom_endpoint = "https://custom-endpoint:9090"
    mock_config.backend.endpoint = custom_endpoint

    session = get_session(mock_config)

    # Verify that the custom endpoint is used for mounting adapters
    assert any(pattern == custom_endpoint for pattern, _ in session.adapters.items())


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://localhost:8080",
        "https://api.example.com",
        "http://127.0.0.1:5000",
    ],
)
def test_various_endpoints(mock_config, endpoint):
    """Test session creation with various endpoint configurations"""
    mock_config.backend.endpoint = endpoint
    session = get_session(mock_config)

    # Verify that the endpoint is used for mounting adapters
    assert any(pattern == endpoint for pattern, _ in session.adapters.items())


@pytest.mark.parametrize(
    ("proxies",),
    (
        ({"http": "http://may-the-force-be-with-you"},),
        ({},),
        ({"https": "https://may-the-force-be-with-you"},),
        (
            {
                "http": "http://may-the-force-be-with-you",
                "https": "https://double-proxy!",
            },
        ),
    ),
)
def test_session_with_proxies(proxies, mock_config):
    mock_config.backend.proxies = proxies

    session = get_session(mock_config)

    assert session.proxies == proxies


def test_session_no_auth(mock_config):
    """No credentials are attached when auth_type is 'none'."""
    mock_config.backend.auth = AuthSchema(auth_type="none")
    session = get_session(mock_config)

    assert session.cert is None
    assert "Authorization" not in session.headers


def test_session_token_auth(mock_config):
    """Bearer token is injected when auth_type is 'token'."""
    mock_config.backend.auth = AuthSchema(auth_type="token", api_key="sk-secret")
    session = get_session(mock_config)

    assert session.cert is None
    assert session.headers.get("Authorization") == "Bearer sk-secret"


def test_session_token_auth_empty_key(mock_config):
    """No Authorization header when auth_type is 'token' but api_key is empty."""
    mock_config.backend.auth = AuthSchema(auth_type="token", api_key="")
    session = get_session(mock_config)

    assert "Authorization" not in session.headers


def test_session_cert_auth(mock_config_cert):
    """Cert tuple is set when auth_type is 'cert'."""
    session = get_session(mock_config_cert)

    assert session.cert is not None
    cert_path, key_path = session.cert
    assert cert_path.name == "cert.pem"
    assert key_path.name == "key.pem"


def test_session_verify_ssl_false(mock_config):
    """verify_ssl=False is passed through to the session."""
    mock_config.backend.auth = AuthSchema(auth_type="none", verify_ssl=False)
    session = get_session(mock_config)

    assert session.verify is False


def test_session_verify_ssl_true(mock_config):
    """verify_ssl=True is passed through to the session."""
    mock_config.backend.auth = AuthSchema(auth_type="none", verify_ssl=True)
    session = get_session(mock_config)

    assert session.verify is True
