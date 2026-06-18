"""Schemas for the backend config."""

import dataclasses
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class AuthSchema:
    """Internal schema that represents the authentication for clad.

    Attributes:
        auth_type (str): Authentication type: "none", "cert", or "token".
        cert_file (Path): Path to the certificate file (used when auth_type="cert").
        key_file (Path): Path to the key file (used when auth_type="cert").
        api_key (str): Bearer token (used when auth_type="token").
        verify_ssl (bool): Whether to verify SSL certificates.
    """

    auth_type: str = "none"
    cert_file: Path = Path("")
    key_file: Path = Path("")
    api_key: str = ""
    verify_ssl: bool = True

    def __post_init__(self) -> None:
        """Post initialization method to normalize values"""
        self.cert_file = Path(self.cert_file).expanduser()
        self.key_file = Path(self.key_file).expanduser()


@dataclasses.dataclass
class BackendSchema:
    """This class represents the [backend] section of our config.toml file.

    Attributes:
        endpoint (str): The endpoint to communicate with.
        proxies (dict[str, str]): Dictionary of proxies to route the request
        auth (Union[dict, AuthSchema]): The authentication information
        timeout (int): HTTP request timeout in seconds
        backend_format (str): API format: "rhsm" for Red Hat Lightspeed, "openai" for OpenAI-compatible APIs.
        model (str): Model name to use when backend_format="openai".
    """

    endpoint: str = "http://localhost:11434/v1"
    auth: AuthSchema = dataclasses.field(default_factory=AuthSchema)
    timeout: int = 60
    backend_format: str = "openai"
    model: str = "llama3"

    proxies: dict[str, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        """Post initialization method to normalize values"""
        # Auth may be present in the config.toml. If it is not, we don't do
        # anything and go with defaults.
        if isinstance(self.auth, dict):
            self.auth = AuthSchema(**self.auth)

        # If the proxies are not set in the config.toml, set the environment variables.
        if not self.proxies:
            http_proxy = os.environ.get("http_proxy")
            if http_proxy:
                self.proxies["http"] = http_proxy

            https_proxy = os.environ.get("https_proxy")
            if https_proxy:
                self.proxies["https"] = https_proxy
