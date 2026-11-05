"""Unit tests for the read-only GitHub App client.

No test performs network I/O: the JWT is signed with an in-memory RSA key and
every HTTP call is served by a small injected stub client.
"""
import base64
import json

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("httpx")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.app.services import github_app as gh


@pytest.fixture(scope="module")
def private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


class _StubResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class _StubHttpClient:
    """Records calls and replays a queue of canned responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[tuple] = []

    def request(self, method, url, headers=None, params=None):
        self.calls.append((method, url, params))
        return self._responses.pop(0)

    def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, json))
        return self._responses.pop(0)

    def close(self):
        pass


def _decode_segment(segment: str) -> dict:
    padded = segment + "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


# ── JWT construction ─────────────────────────────────────────────────────────

def test_build_app_jwt_has_three_segments(private_key_pem):
    assert gh.build_app_jwt("123", private_key_pem).count(".") == 2


def test_jwt_claims_respect_github_limits(private_key_pem):
    token = gh.build_app_jwt("123", private_key_pem, now=1_000_000)
    header, payload, _ = token.split(".")
    assert _decode_segment(header)["alg"] == "RS256"
    claims = _decode_segment(payload)
    assert claims["iss"] == "123"
    ttl = claims["exp"] - claims["iat"]
    assert 0 < ttl <= 600
    # iat is skewed into the past to tolerate clock drift.
    assert claims["iat"] == 1_000_000 - 60


def test_jwt_ttl_is_capped_at_github_maximum(private_key_pem):
    token = gh.build_app_jwt("123", private_key_pem, now=1_000_000, ttl_seconds=10_000)
    _, payload, _ = token.split(".")
    claims = _decode_segment(payload)
    assert claims["exp"] - claims["iat"] == 600


def test_build_app_jwt_requires_credentials():
    with pytest.raises(gh.GitHubAppNotConfigured):
        gh.build_app_jwt("", "")


def test_build_app_jwt_rejects_non_pem():
    with pytest.raises(gh.GitHubAppError):
        gh.build_app_jwt("123", "not-a-pem")


def test_unescape_pem_converts_literal_newlines(private_key_pem):
    assert gh.unescape_pem(private_key_pem.replace("\n", "\\n")) == private_key_pem.strip()


# ── configuration helpers ────────────────────────────────────────────────────

def test_missing_env_vars_lists_everything_when_unset(monkeypatch):
    for name in gh.GITHUB_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert set(gh.GitHubAppClient.missing_env_vars()) == set(gh.GITHUB_ENV_VARS)
    assert gh.GitHubAppClient.is_configured() is False


def test_is_configured_true_when_all_present(monkeypatch):
    for name in gh.GITHUB_ENV_VARS:
        monkeypatch.setenv(name, "value")
    assert gh.GitHubAppClient.missing_env_vars() == []
    assert gh.GitHubAppClient.is_configured() is True


# ── read-only allow-list ─────────────────────────────────────────────────────

@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_client_refuses_content_writes(private_key_pem, method):
    client = gh.GitHubAppClient(app_id="1", private_key_pem=private_key_pem)
    with pytest.raises(gh.GitHubAppError):
        client._api_request(method, "/repos/o/r/contents/file")


def test_client_refuses_a_post_to_a_non_token_path(private_key_pem):
    client = gh.GitHubAppClient(app_id="1", private_key_pem=private_key_pem)
    with pytest.raises(gh.GitHubAppError):
        client._api_request("POST", "/repos/o/r/issues")


# ── installation-scoped reads ────────────────────────────────────────────────

def test_list_repositories_returns_installation_repositories(private_key_pem):
    http = _StubHttpClient([_StubResponse(200, {"repositories": [{"full_name": "o/r"}]})])
    client = gh.GitHubAppClient(app_id="1", private_key_pem=private_key_pem, http_client=http)
    assert client.list_repositories("installation-token") == [{"full_name": "o/r"}]
    method, url, _ = http.calls[0]
    assert method == "GET" and url.endswith("/installation/repositories")


def test_get_file_content_decodes_utf8(private_key_pem):
    payload = base64.b64encode(b"col_a,col_b\n1,2\n").decode()
    http = _StubHttpClient([
        _StubResponse(200, {
            "type": "file", "size": 14, "encoding": "base64",
            "content": payload, "path": "a.csv", "sha": "abc",
        })
    ])
    client = gh.GitHubAppClient(app_id="1", private_key_pem=private_key_pem, http_client=http)
    result = client.get_file_content("o", "r", "a.csv", "main", installation_token="t")
    assert result["encoding"] == "utf-8"
    assert result["content"].startswith("col_a")
    assert result["sha"] == "abc"


def test_get_file_content_flags_binary_content(private_key_pem):
    payload = base64.b64encode(b"\xff\xfe\x00\x01").decode()
    http = _StubHttpClient([
        _StubResponse(200, {"type": "file", "size": 4, "encoding": "base64", "content": payload, "path": "b", "sha": "s"})
    ])
    client = gh.GitHubAppClient(app_id="1", private_key_pem=private_key_pem, http_client=http)
    result = client.get_file_content("o", "r", "b", "main", installation_token="t")
    assert result == {"unsupported": True, "reason": "binary_content"}


def test_get_file_content_flags_oversized_files(private_key_pem):
    raw = b"x" * 500
    http = _StubHttpClient([
        _StubResponse(200, {
            "type": "file", "size": len(raw), "encoding": "base64",
            "content": base64.b64encode(raw).decode(), "path": "big", "sha": "s",
        })
    ])
    client = gh.GitHubAppClient(
        app_id="1", private_key_pem=private_key_pem, http_client=http, max_file_bytes=100
    )
    result = client.get_file_content("o", "r", "big", "main", installation_token="t")
    assert result["unsupported"] is True
    assert result["reason"] == "file_too_large"


def test_api_error_surfaces_status_and_message(private_key_pem):
    http = _StubHttpClient([_StubResponse(404, {"message": "Not Found"})])
    client = gh.GitHubAppClient(app_id="1", private_key_pem=private_key_pem, http_client=http)
    with pytest.raises(gh.GitHubAppApiError) as excinfo:
        client.list_repositories("t")
    assert excinfo.value.status_code == 404
    assert "Not Found" in excinfo.value.message
