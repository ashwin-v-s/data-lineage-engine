"""Workspace API keys: minting, hashing and display helpers.

A key is shown to its creator exactly once.  The server keeps only a SHA-256
hash of the secret plus a short display prefix, so a database dump cannot be
replayed against the API.  Keys are deliberately read-only: they may call the
catalog read surface and nothing that mutates workspace state.
"""
from __future__ import annotations

import hashlib
import secrets

# Every Kairos-issued key starts with this marker, which lets the auth layer
# tell an API key apart from a Supabase access token before any network call.
API_KEY_PREFIX = "kairos_sk_"

# Length of the stored display prefix (the marker plus random characters).
PREFIX_LENGTH = 20

# Read surfaces an API key is allowed to reach.  Anything else is refused even
# when the request is a GET, so a key can never read member emails, webhook
# secrets or source connection records.
READ_ALLOWED_PREFIXES: tuple[str, ...] = (
    "/api/v1/catalog",
    "/api/v1/assets",
    "/api/v1/lineage",
    "/api/v1/search",
    "/api/v1/health",
    "/api/v1/api-keys/self",
)


def hash_secret(raw_key: str) -> str:
    """Return the hex SHA-256 digest persisted in ``workspace_api_key``."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Mint a key.

    Returns ``(token, display_prefix, secret_hash)`` where ``token`` is the only
    copy of the secret the caller will ever see.
    """
    body = secrets.token_urlsafe(32)
    token = f"{API_KEY_PREFIX}{body}"
    return token, display_prefix(token), hash_secret(token)


def display_prefix(token: str) -> str:
    """Return the stored prefix used to identify a key in the UI."""
    return token[:PREFIX_LENGTH]


def is_api_key(token: str) -> bool:
    return bool(token) and token.startswith(API_KEY_PREFIX)


def path_allowed(path: str) -> bool:
    """True when an API key may read this path.

    Matching is on a path boundary so ``/api/v1/assets-malicious`` does not
    inherit the ``/api/v1/assets`` grant.
    """
    return any(path == prefix or path.startswith(prefix + "/") for prefix in READ_ALLOWED_PREFIXES)


def key_principal(key: dict) -> dict:
    """Build the request principal recorded on ``request.state`` for a key.

    ``id`` is namespaced so a key can never impersonate a real user row, and
    ``auth`` lets routes and logs distinguish the two credential types.
    """
    return {
        "id": f"api-key:{key['key_id']}",
        "email": None,
        "auth": "api_key",
        "api_key_id": key["key_id"],
        "scopes": tuple(key.get("scopes") or ("read",)),
        "workspace_id": key["workspace_id"],
        "key_name": key.get("name"),
    }
