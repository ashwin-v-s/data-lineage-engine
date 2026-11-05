"""
backend/app/services/github_app.py
──────────────────────────────────
Minimal, read-only GitHub App client used by the private-repository connector.

Responsibilities
────────────────
* Build the short-lived GitHub App JWT (RS256) from ``GITHUB_APP_ID`` and
  ``GITHUB_APP_PRIVATE_KEY``.  Signed directly with ``cryptography``
  (RSASSA-PKCS1v15 + SHA-256); no JWT library is added.
* Exchange an installation for a short-lived installation access token.
* List installations and repositories, read a repository tree, and read a file
  blob.

Safety posture
──────────────
* The only non-GET call this module can make is minting an installation token
  (``POST /app/installations/{id}/access_tokens``).  Every repository-content
  call is a GET; POST/PATCH/PUT/DELETE against repository content is refused.
* Files are size-capped and must be UTF-8 decodable; anything else is reported
  as ``{"unsupported": True, "reason": ...}`` and never silently truncated.
* Every method takes its credentials from the instance, and the HTTP client is
  injectable, so no test needs network access.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

APP_ID_ENV = "GITHUB_APP_ID"
PRIVATE_KEY_ENV = "GITHUB_APP_PRIVATE_KEY"
SLUG_ENV = "GITHUB_APP_SLUG"
CLIENT_ID_ENV = "GITHUB_APP_CLIENT_ID"
CLIENT_SECRET_ENV = "GITHUB_APP_CLIENT_SECRET"
CALLBACK_URL_ENV = "GITHUB_APP_CALLBACK_URL"

# Every GitHub environment variable the connector needs to be "configured".
GITHUB_ENV_VARS = (
    APP_ID_ENV,
    PRIVATE_KEY_ENV,
    SLUG_ENV,
    CLIENT_ID_ENV,
    CLIENT_SECRET_ENV,
    CALLBACK_URL_ENV,
)

DEFAULT_API_BASE = "https://api.github.com"
DEFAULT_OAUTH_BASE = "https://github.com"
API_VERSION = "2022-11-28"
ACCEPT = "application/vnd.github+json"
DEFAULT_MAX_FILE_BYTES = 1_000_000

# GitHub requires exp <= 10 minutes in the future; issue iat 60s in the past.
_JWT_IAT_SKEW_SECONDS = 60
_JWT_TTL_SECONDS = 540


class GitHubAppError(RuntimeError):
    """Base error for GitHub App operations."""


class GitHubAppNotConfigured(GitHubAppError):
    """Raised when a required GitHub App credential is missing."""


class GitHubAppApiError(GitHubAppError):
    """Raised when GitHub returns an unexpected error response."""

    def __init__(self, status_code: int, message: str):
        super().__init__(f"GitHub API returned {status_code}: {message}")
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class InstallationToken:
    token: str
    expires_at: datetime


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unescape_pem(value: str) -> str:
    """Turn a single-line PEM with literal ``\\n`` escapes into a real PEM."""
    return value.replace("\\n", "\n").strip()


def _private_key_from_env() -> str | None:
    raw = os.getenv(PRIVATE_KEY_ENV)
    return unescape_pem(raw) if raw else None


def build_app_jwt(
    app_id: str,
    private_key_pem: str,
    *,
    now: int | None = None,
    ttl_seconds: int = _JWT_TTL_SECONDS,
) -> str:
    """Return a signed GitHub App JWT (RS256).

    ``iat`` is set one minute in the past to tolerate clock drift and ``exp`` is
    ``iat + 600`` seconds, exactly at GitHub's ten-minute ceiling.  ``ttl_seconds``
    may be lowered but never exceeds 600.
    """
    if not app_id or not private_key_pem:
        raise GitHubAppNotConfigured("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY are required")
    ttl = min(int(ttl_seconds), 600)
    issued_at = int(now if now is not None else time.time()) - _JWT_IAT_SKEW_SECONDS
    expires_at = issued_at + ttl

    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps({"iat": issued_at, "exp": expires_at, "iss": str(app_id)}, separators=(",", ":")).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    try:
        key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    except (ValueError, TypeError) as exc:
        raise GitHubAppError("GITHUB_APP_PRIVATE_KEY is not a valid PEM private key") from exc
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64url(signature)}"


class GitHubAppClient:
    """Injectable, read-only GitHub App client."""

    def __init__(
        self,
        *,
        app_id: str | None = None,
        private_key_pem: str | None = None,
        slug: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        callback_url: str | None = None,
        api_base: str = DEFAULT_API_BASE,
        oauth_base: str = DEFAULT_OAUTH_BASE,
        http_client: httpx.Client | None = None,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        clock=time.time,
    ) -> None:
        self.app_id = app_id if app_id is not None else os.getenv(APP_ID_ENV)
        if private_key_pem is not None:
            self.private_key_pem = unescape_pem(private_key_pem)
        else:
            self.private_key_pem = _private_key_from_env()
        self.slug = slug if slug is not None else os.getenv(SLUG_ENV)
        self.client_id = client_id if client_id is not None else os.getenv(CLIENT_ID_ENV)
        self.client_secret = client_secret if client_secret is not None else os.getenv(CLIENT_SECRET_ENV)
        self.callback_url = callback_url if callback_url is not None else os.getenv(CALLBACK_URL_ENV)
        self.api_base = api_base.rstrip("/")
        self.oauth_base = oauth_base.rstrip("/")
        self.max_file_bytes = max_file_bytes
        self._clock = clock
        self._client = http_client

    # ── configuration helpers ────────────────────────────────────────────────
    @staticmethod
    def missing_env_vars() -> list[str]:
        """Return the required GitHub environment variables that are absent."""
        return [name for name in GITHUB_ENV_VARS if not (os.getenv(name) or "").strip()]

    @staticmethod
    def is_configured() -> bool:
        return not GitHubAppClient.missing_env_vars()

    def _require_app_credentials(self) -> None:
        if not self.app_id or not self.private_key_pem:
            raise GitHubAppNotConfigured("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY are required")

    def app_jwt(self) -> str:
        self._require_app_credentials()
        return build_app_jwt(self.app_id, self.private_key_pem, now=int(self._clock()))

    # ── HTTP plumbing ────────────────────────────────────────────────────────
    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=10.0)
        return self._client

    @staticmethod
    def _base_headers() -> dict[str, str]:
        return {"Accept": ACCEPT, "X-GitHub-Api-Version": API_VERSION}

    def _api_request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Issue an API request, enforcing the read-only allow-list."""
        method = method.upper()
        read_only_ok = method == "GET"
        token_mint_ok = method == "POST" and path.endswith("/access_tokens")
        if not (read_only_ok or token_mint_ok):
            raise GitHubAppError(
                f"read-only GitHub client refused {method} {path}; repository content is GET-only"
            )
        headers = self._base_headers()
        headers["Authorization"] = f"Bearer {token}" if token else f"Bearer {self.app_jwt()}"
        response = self._http().request(method, f"{self.api_base}{path}", headers=headers, params=params)
        return response

    def _json(self, response: httpx.Response) -> dict | list:
        if response.status_code >= 400:
            raise GitHubAppApiError(response.status_code, _safe_message(response))
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubAppApiError(response.status_code, "GitHub returned a non-JSON response") from exc

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    # ── app-level operations ─────────────────────────────────────────────────
    def list_installations(self) -> list[dict]:
        """GET /app/installations — installations visible to this app."""
        data = self._json(self._api_request("GET", "/app/installations", params={"per_page": 100}))
        if isinstance(data, dict):
            data = data.get("installations", [])
        return list(data)

    def get_installation(self, installation_id: int) -> dict:
        """GET /app/installations/{id} — the installation (account login/type)."""
        return self._json(self._api_request("GET", f"/app/installations/{int(installation_id)}"))

    def create_installation_token(self, installation_id: int) -> InstallationToken:
        """POST /app/installations/{id}/access_tokens — mint an installation token."""
        data = self._json(
            self._api_request("POST", f"/app/installations/{int(installation_id)}/access_tokens")
        )
        token = data.get("token") if isinstance(data, dict) else None
        expires_at = data.get("expires_at") if isinstance(data, dict) else None
        if not token or not expires_at:
            raise GitHubAppApiError(200, "installation token response was missing token/expires_at")
        return InstallationToken(token=token, expires_at=_parse_timestamp(expires_at))

    def exchange_user_code(self, code: str) -> str:
        """Exchange an OAuth ``code`` for a user access token (login host, not the API)."""
        if not self.client_id or not self.client_secret:
            raise GitHubAppNotConfigured("GITHUB_APP_CLIENT_ID and GITHUB_APP_CLIENT_SECRET are required")
        response = self._http().post(
            f"{self.oauth_base}/login/oauth/access_token",
            headers={"Accept": "application/json", "X-GitHub-Api-Version": API_VERSION},
            json={"client_id": self.client_id, "client_secret": self.client_secret, "code": code},
        )
        data = self._json(response)
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise GitHubAppApiError(response.status_code, "OAuth code exchange returned no access_token")
        return token

    def resolve_installation(self, installation_id: int, *, code: str | None = None) -> dict:
        """Return the installation record for ``installation_id``.

        With a ``code``, the code is exchanged for a user token and GitHub's
        ``/user/installations`` is consulted, which also proves the authorizing
        user can reach the installation.  Without a code, the app can read the
        installation directly.
        """
        if code:
            user_token = self.exchange_user_code(code)
            data = self._json(
                self._api_request("GET", "/user/installations", token=user_token, params={"per_page": 100})
            )
            installations = data.get("installations", []) if isinstance(data, dict) else list(data)
            for installation in installations:
                if str(installation.get("id")) == str(installation_id):
                    return installation
            raise GitHubAppApiError(404, f"installation {installation_id} is not accessible to the authorizing user")
        return self.get_installation(installation_id)

    # ── installation-scoped reads ────────────────────────────────────────────
    def list_repositories(self, installation_token: str) -> list[dict]:
        """GET /installation/repositories — repositories the installation can read."""
        data = self._json(
            self._api_request("GET", "/installation/repositories", token=installation_token, params={"per_page": 100})
        )
        repositories = data.get("repositories", []) if isinstance(data, dict) else list(data)
        return list(repositories)

    def get_tree(self, owner: str, repo: str, ref: str, *, installation_token: str, recursive: bool = True) -> dict:
        """GET /repos/{owner}/{repo}/git/trees/{ref} — the repository tree."""
        params = {"recursive": "1"} if recursive else None
        return self._json(
            self._api_request(
                "GET",
                f"/repos/{owner}/{repo}/git/trees/{ref}",
                token=installation_token,
                params=params,
            )
        )

    def get_file_content(self, owner: str, repo: str, path: str, ref: str, *, installation_token: str) -> dict:
        """GET /repos/{owner}/{repo}/contents/{path} — a single file blob.

        Returns the supported shape ``{"path","ref","sha","encoding","size","content"}``
        or ``{"unsupported": True, "reason": ...}`` for binary/oversized content.
        """
        response = self._api_request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            token=installation_token,
            params={"ref": ref},
        )
        if response.status_code == 403:
            # The contents API returns 403 for files it will not inline (too large).
            return {"unsupported": True, "reason": "github_refused_contents_request", "detail": _safe_message(response)}
        if response.status_code == 404:
            raise GitHubAppApiError(404, f"{owner}/{repo}@{ref}:{path} was not found")
        data = self._json(response)
        if not isinstance(data, dict) or data.get("type") != "file":
            return {"unsupported": True, "reason": "not_a_file"}
        declared_size = data.get("size")
        if isinstance(declared_size, int) and declared_size > self.max_file_bytes:
            return {
                "unsupported": True,
                "reason": "file_too_large",
                "detail": f"size {declared_size} exceeds the {self.max_file_bytes}-byte limit",
            }
        if data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
            return {"unsupported": True, "reason": "unsupported_encoding"}
        try:
            raw = base64.b64decode(data["content"], validate=False)
        except (binascii.Error, ValueError):
            return {"unsupported": True, "reason": "content_not_base64"}
        if len(raw) > self.max_file_bytes:
            return {
                "unsupported": True,
                "reason": "file_too_large",
                "detail": f"decoded size {len(raw)} exceeds the {self.max_file_bytes}-byte limit",
            }
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {"unsupported": True, "reason": "binary_content"}
        return {
            "path": data.get("path", path),
            "ref": ref,
            "sha": data.get("sha"),
            "encoding": "utf-8",
            "size": len(raw),
            "content": text,
        }


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def _safe_message(response: httpx.Response) -> str:
    """A short, non-leaking error description from a GitHub error response."""
    try:
        body = response.json()
    except ValueError:
        return (response.text or "")[:200] or "no response body"
    if isinstance(body, dict):
        message = body.get("message")
        if isinstance(message, str):
            return message[:200]
    return "unexpected GitHub error response"
