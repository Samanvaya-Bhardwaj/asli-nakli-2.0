"""Ed25519 request signatures between nodes (PLAN.md section 8.2).

The signed message is METHOD, path with query, unix time and caller org id, one per line.
"""

import base64
import binascii
import os
from collections.abc import Callable, Mapping
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

MAX_CLOCK_SKEW_S = 120
H_ORG, H_TIME, H_SIG = "X-Asali-Org", "X-Asali-Time", "X-Asali-Signature"


class ShareAuthError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def load_or_create_keys(data_dir: Path) -> Ed25519PrivateKey:
    path = data_dir / "keys" / "node_ed25519.pem"
    if path.exists():
        key = load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"{path} is not an Ed25519 key")
        return key
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    os.chmod(path, 0o600)
    return key


def public_key_b64(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def _message(method: str, path_with_query: str, stamp: str, org_id: str) -> bytes:
    return f"{method.upper()}\n{path_with_query}\n{stamp}\n{org_id}".encode()


def sign_request(key: Ed25519PrivateKey, org_id: str, method: str, path_with_query: str, now: int) -> dict[str, str]:
    signature = key.sign(_message(method, path_with_query, str(now), org_id))
    return {H_ORG: org_id, H_TIME: str(now), H_SIG: base64.b64encode(signature).decode()}


def verify_request(
    headers: Mapping[str, str],
    method: str,
    path_with_query: str,
    now: int | float,
    lookup: Callable[[str], str | None],
    max_skew: int = MAX_CLOCK_SKEW_S,
) -> str:
    """Return the caller's org id, or raise ShareAuthError(unknown_org | clock_skew | bad_signature)."""
    h = {k.lower(): v for k, v in headers.items()}
    org_id = h.get(H_ORG.lower(), "")
    stamp = h.get(H_TIME.lower(), "")
    public = lookup(org_id) if org_id else None
    if public is None:
        raise ShareAuthError("unknown_org")
    if not stamp.isdigit() or abs(now - int(stamp)) > max_skew:
        raise ShareAuthError("clock_skew")
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public))
        key.verify(base64.b64decode(h.get(H_SIG.lower(), "")), _message(method, path_with_query, stamp, org_id))
    except (InvalidSignature, ValueError, binascii.Error):
        raise ShareAuthError("bad_signature") from None
    return org_id
