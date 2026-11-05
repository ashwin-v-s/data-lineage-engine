"""Unit tests for GitHub token encryption and signed OAuth state.

The module under test performs no I/O, so these tests need no network and no
database.  Every test that touches encryption runs with a valid key injected
through ``KAIROS_TOKEN_ENCRYPTION_KEY``; the fail-closed tests deliberately
remove or corrupt it.
"""
import base64

import pytest

pytest.importorskip("cryptography")

from backend.app.services import token_crypto as tc


@pytest.fixture(autouse=True)
def _valid_key(monkeypatch):
    """Every test starts with one valid, random AES-256 key configured."""
    monkeypatch.setenv(tc.ENCRYPTION_KEY_ENV, tc.generate_key())


def test_encrypt_decrypt_round_trip():
    ciphertext = tc.encrypt_token("ghs_installation_token_value")
    assert isinstance(ciphertext, bytes)
    # The plaintext must not survive in the envelope.
    assert b"ghs_installation_token_value" not in ciphertext
    assert tc.decrypt_token(ciphertext) == "ghs_installation_token_value"


def test_envelope_is_self_describing():
    ciphertext = tc.encrypt_token("token")
    assert ciphertext.startswith(b"KGC1")
    assert ciphertext[4] == tc.current_key_version()


def test_each_encryption_uses_a_fresh_nonce():
    assert tc.encrypt_token("same") != tc.encrypt_token("same")


def test_empty_token_is_rejected():
    with pytest.raises(tc.TokenCryptoError):
        tc.encrypt_token("")


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.delenv(tc.ENCRYPTION_KEY_ENV, raising=False)
    assert tc.is_configured() is False
    with pytest.raises(tc.TokenCryptoError):
        tc.encrypt_token("token")


def test_non_base64_key_fails_closed(monkeypatch):
    monkeypatch.setenv(tc.ENCRYPTION_KEY_ENV, "not*base64*")
    assert tc.is_configured() is False
    with pytest.raises(tc.TokenCryptoError):
        tc.load_key()


def test_wrong_length_key_fails_closed(monkeypatch):
    monkeypatch.setenv(tc.ENCRYPTION_KEY_ENV, base64.urlsafe_b64encode(b"short").decode())
    assert tc.is_configured() is False
    with pytest.raises(tc.TokenCryptoError):
        tc.load_key()


def test_tampered_ciphertext_is_rejected():
    ciphertext = bytearray(tc.encrypt_token("token"))
    ciphertext[-1] ^= 0x01
    with pytest.raises(tc.TokenCryptoError):
        tc.decrypt_token(bytes(ciphertext))


def test_decrypting_with_a_different_key_is_rejected(monkeypatch):
    ciphertext = tc.encrypt_token("token")
    monkeypatch.setenv(tc.ENCRYPTION_KEY_ENV, tc.generate_key())
    with pytest.raises(tc.TokenCryptoError):
        tc.decrypt_token(ciphertext)


def test_foreign_bytes_are_not_accepted_as_an_envelope():
    with pytest.raises(tc.TokenCryptoError):
        tc.decrypt_token(b"plaintext-that-is-not-an-envelope")


def test_signed_state_round_trip():
    state = tc.sign_state("user-1", "workspace-1")
    verified = tc.verify_state(state)
    assert verified["user_id"] == "user-1"
    assert verified["workspace_id"] == "workspace-1"


def test_signed_state_requires_both_identifiers():
    with pytest.raises(tc.TokenCryptoError):
        tc.sign_state("", "workspace-1")


def test_malformed_state_is_rejected():
    for bad in ("", "no-separator", "a.b.c"):
        with pytest.raises(tc.SignedStateError):
            tc.verify_state(bad)


def test_tampered_state_is_rejected():
    state = tc.sign_state("user-1", "workspace-1")
    payload, signature = state.split(".", 1)
    forged = f"{payload}.{'A' * len(signature)}"
    with pytest.raises(tc.SignedStateError):
        tc.verify_state(forged)


def test_expired_state_is_rejected():
    state = tc.sign_state("user-1", "workspace-1", now=1_000_000)
    assert tc.verify_state(state, now=1_000_000)["user_id"] == "user-1"
    with pytest.raises(tc.SignedStateError):
        tc.verify_state(state, now=1_000_000 + tc.STATE_TTL_SECONDS + 1)


def test_state_issued_in_the_future_is_rejected():
    state = tc.sign_state("user-1", "workspace-1", now=2_000_000)
    with pytest.raises(tc.SignedStateError):
        tc.verify_state(state, now=1_000_000)
