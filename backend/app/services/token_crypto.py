"""
backend/app/services/token_crypto.py
────────────────────────────────────
Authenticated encryption for GitHub App installation tokens at rest, plus the
HMAC-signed OAuth state used by the install/callback flow.

Design rules
────────────
* All encryption keys come from a single environment variable,
  ``KAIROS_TOKEN_ENCRYPTION_KEY``, which must be a urlsafe base64 encoding of
  exactly 32 random bytes (an AES-256 key).
* The module **fails closed**: a missing or malformed key raises a clear error
  and there is *no* plaintext fallback anywhere in this module.
* ``token_ciphertext`` is a self-describing envelope (magic + key version +
  AES-GCM nonce + ciphertext) so the stored ``token_key_version`` column can
  drive key rotation later without ambiguity.
* The state helper signs ``(user_id, workspace_id, issued_at)`` with
  HMAC-SHA256 keyed by the same secret, so no new table is required and the
  state is bound to the signed-in user and their workspace.

Nothing here performs I/O or network calls.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import os
import time

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Environment variable that holds the urlsafe-base64 AES-256 key.
ENCRYPTION_KEY_ENV = "KAIROS_TOKEN_ENCRYPTION_KEY"

# Version written into newly minted ciphertexts.  Stored verbatim in the
# ``github_connection.token_key_version`` column.  Bump alongside a new key to
# support rotation.
_CURRENT_KEY_VERSION = 1

# Envelope magic.  Versioned so a future format change is detectable.
_MAGIC = b"KGC1"
_NONCE_BYTES = 12
_KEY_BYTES = 32

# Signed-state default lifetime.
STATE_TTL_SECONDS = 600


class TokenCryptoError(RuntimeError):
    """Raised when token encryption/decryption cannot proceed safely."""


class SignedStateError(ValueError):
    """Raised when a signed install/callback state is invalid or expired."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def load_key() -> bytes:
    """Return the raw 32-byte AES key, or raise :class:`TokenCryptoError`.

    This never silently degrades: an unset, non-base64, or wrong-length key is
    always an error.
    """
    raw = os.getenv(ENCRYPTION_KEY_ENV)
    if not raw or not raw.strip():
        raise TokenCryptoError(
            f"{ENCRYPTION_KEY_ENV} is not configured; refusing to handle GitHub tokens"
        )
    try:
        key = base64.urlsafe_b64decode(raw.strip().encode("ascii"))
    except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
        raise TokenCryptoError(
            f"{ENCRYPTION_KEY_ENV} is not valid urlsafe base64"
        ) from exc
    if len(key) != _KEY_BYTES:
        raise TokenCryptoError(
            f"{ENCRYPTION_KEY_ENV} must decode to exactly {_KEY_BYTES} bytes; got {len(key)}"
        )
    return key


def is_configured() -> bool:
    """True only when a structurally valid key is present (never raises)."""
    try:
        load_key()
    except TokenCryptoError:
        return False
    return True


def generate_key() -> str:
    """Generate a fresh urlsafe-base64 AES-256 key (for operators and tests)."""
    return base64.urlsafe_b64encode(os.urandom(_KEY_BYTES)).decode("ascii")


def current_key_version() -> int:
    """Key version written into new ciphertexts and stored with the connection."""
    return _CURRENT_KEY_VERSION


def encrypt_token(plaintext: str, *, key_version: int | None = None) -> bytes:
    """Encrypt a token string with AES-256-GCM.

    Returns the self-describing envelope.  Raises :class:`TokenCryptoError` for
    any problem, including a missing/invalid key.
    """
    if not isinstance(plaintext, str) or not plaintext:
        raise TokenCryptoError("refusing to encrypt an empty token")
    version = _CURRENT_KEY_VERSION if key_version is None else key_version
    if not 0 <= version <= 255:
        raise TokenCryptoError(f"key version {version} does not fit in one byte")
    key = load_key()
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return _MAGIC + bytes([version]) + nonce + ciphertext


def decrypt_token(ciphertext: bytes | bytearray | memoryview) -> str:
    """Decrypt an envelope produced by :func:`encrypt_token`.

    A tampered ciphertext (or the wrong key) raises :class:`TokenCryptoError`
    via the AES-GCM authentication tag check.
    """
    if ciphertext is None:
        raise TokenCryptoError("no ciphertext supplied")
    data = bytes(ciphertext)
    header = len(_MAGIC) + 1
    if len(data) < header + _NONCE_BYTES or not data.startswith(_MAGIC):
        raise TokenCryptoError("ciphertext is not in the expected Kairos envelope")
    version = data[len(_MAGIC)]
    if version != _CURRENT_KEY_VERSION:
        raise TokenCryptoError(
            f"ciphertext was written with key version {version}, but only version "
            f"{_CURRENT_KEY_VERSION} is configured; restore the previous key or rotate explicitly"
        )
    nonce = data[header : header + _NONCE_BYTES]
    body = data[header + _NONCE_BYTES :]
    try:
        plaintext = AESGCM(load_key()).decrypt(nonce, body, None)
    except InvalidTag as exc:
        raise TokenCryptoError(
            "ciphertext failed authentication (tampered or encrypted with a different key)"
        ) from exc
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover - envelope is UTF-8 by construction
        raise TokenCryptoError("decrypted token is not valid UTF-8") from exc


def sign_state(
    user_id: str,
    workspace_id: str,
    *,
    ttl_seconds: int = STATE_TTL_SECONDS,
    now: int | None = None,
) -> str:
    """Return a urlsafe signed state binding a user and workspace to an issue time."""
    if not user_id or not workspace_id:
        raise TokenCryptoError("state requires both a user id and a workspace id")
    issued_at = int(now if now is not None else time.time())
    payload = json.dumps(
        {"v": 1, "u": user_id, "w": workspace_id, "iat": issued_at},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_segment = _b64url_encode(payload)
    signature = hmac.new(load_key(), payload_segment.encode("ascii"), "sha256").digest()
    return f"{payload_segment}.{_b64url_encode(signature)}"


def verify_state(
    state: str,
    *,
    ttl_seconds: int = STATE_TTL_SECONDS,
    now: int | None = None,
) -> dict:
    """Verify a state string, returning ``{"user_id", "workspace_id", "issued_at"}``.

    Raises :class:`SignedStateError` (a ``ValueError``) for a missing, malformed,
    tampered, or expired state.
    """
    if not state or not isinstance(state, str) or state.count(".") != 1:
        raise SignedStateError("state is missing or malformed")
    payload_segment, signature_segment = state.split(".", 1)
    try:
        expected = hmac.new(
            load_key(), payload_segment.encode("ascii"), "sha256"
        ).digest()
        provided = _b64url_decode(signature_segment)
    except (TokenCryptoError, binascii.Error, ValueError) as exc:
        raise SignedStateError("state signature could not be decoded") from exc
    if not hmac.compare_digest(expected, provided):
        raise SignedStateError("state signature does not match")
    try:
        payload = json.loads(_b64url_decode(payload_segment))
    except (binascii.Error, ValueError, json.JSONDecodeError) as exc:
        raise SignedStateError("state payload is not valid") from exc
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise SignedStateError("state payload version is not supported")
    user_id = payload.get("u")
    workspace_id = payload.get("w")
    issued_at = payload.get("iat")
    if not isinstance(user_id, str) or not isinstance(workspace_id, str) or not isinstance(issued_at, int):
        raise SignedStateError("state payload is incomplete")
    current = int(now if now is not None else time.time())
    if issued_at - current > 60:
        raise SignedStateError("state was issued in the future")
    if current - issued_at > ttl_seconds:
        raise SignedStateError("state has expired")
    return {"user_id": user_id, "workspace_id": workspace_id, "issued_at": issued_at}
