"""The guard's stdlib Ed25519 verifier agrees with the `cryptography` package (which the approver signs with)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ed25519_verify  # noqa: E402

crypto = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
serialization = pytest.importorskip("cryptography.hazmat.primitives.serialization")


def raw_pub(key) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


@pytest.mark.parametrize("message", [b"", b"x", b'{"d_id":"D-PAY-3","sha256":"ab"}' * 20])
def test_valid_signatures_verify(message):
    k = crypto.Ed25519PrivateKey.generate()
    assert ed25519_verify.verify(raw_pub(k), message, k.sign(message))


def test_tampering_is_rejected():
    k, other = crypto.Ed25519PrivateKey.generate(), crypto.Ed25519PrivateKey.generate()
    m = b'{"d_id":"D-PAY-3"}'
    sig = k.sign(m)
    assert not ed25519_verify.verify(raw_pub(k), m + b" ", sig)                      # message changed
    assert not ed25519_verify.verify(raw_pub(other), m, sig)                         # wrong key
    assert not ed25519_verify.verify(raw_pub(k), m, sig[:-1] + bytes([sig[-1] ^ 1]))  # signature changed
    assert not ed25519_verify.verify(raw_pub(k), m, b"\0" * 64)
    assert not ed25519_verify.verify(b"\0" * 31, m, sig)
