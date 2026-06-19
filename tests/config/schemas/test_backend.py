import pytest

from command_line_assistant.config.schemas.backend import AuthSchema, BackendSchema


def test_auth_schema_defaults():
    auth = AuthSchema()
    assert auth.auth_type == "none"
    assert auth.api_key == ""
    assert auth.verify_ssl is True


def test_auth_schema_cert_mode():
    auth = AuthSchema(auth_type="cert", cert_file="/tmp/cert.pem", key_file="/tmp/key.pem")
    assert auth.auth_type == "cert"
    assert str(auth.cert_file) == "/tmp/cert.pem"
    assert str(auth.key_file) == "/tmp/key.pem"


def test_auth_schema_token_mode():
    auth = AuthSchema(auth_type="token", api_key="sk-test")
    assert auth.auth_type == "token"
    assert auth.api_key == "sk-test"


def test_backend_schema_defaults():
    backend = BackendSchema()
    assert backend.endpoint == "http://localhost:11434/v1"
    assert backend.backend_format == "openai"
    assert backend.model == "llama3"
    assert backend.timeout == 60


def test_backend_schema_from_dict():
    backend = BackendSchema(auth={"auth_type": "none", "verify_ssl": False})
    assert backend.auth.auth_type == "none"
    assert backend.auth.verify_ssl is False


@pytest.mark.parametrize("auth_type", ["none", "cert", "token"])
def test_auth_schema_valid_auth_types(auth_type):
    auth = AuthSchema(auth_type=auth_type)
    assert auth.auth_type == auth_type
