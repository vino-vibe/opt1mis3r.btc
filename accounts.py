"""
accounts.py — single source of truth for which accounts exist and what their
iPhone fingerprint is.

.env contract:
    ACCOUNTS=HDERDAR,RAINCANE,RAINALT     # comma-separated list of account names
    HDERDAR=<auth_info>                    # the auth-info header value
    HDERDAR_DEVICE_UUID=...                # uppercase iOS-style UUID
    HDERDAR_DEVICE_NAME=iPhone15,3
    HDERDAR_APP_VERSION=31

Per-account variables fall back to a global default if not set:
    DEFAULT_DEVICE_UUID, DEFAULT_DEVICE_NAME, DEFAULT_APP_VERSION

Every script imports from here instead of redefining its own AUTH_INFOS dict.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from client import AccountFingerprint

# Load .env once from the repo root; idempotent if called multiple times.
load_dotenv(Path(__file__).with_name(".env"))


def _required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def _with_fallback(per_account: str, default: str) -> str | None:
    """Per-account value, falling back to a DEFAULT_* value."""
    return os.getenv(per_account) or os.getenv(default)


def list_account_names() -> list[str]:
    """Names declared by the ACCOUNTS env var (comma-separated)."""
    raw = os.getenv("ACCOUNTS", "")
    return [n.strip() for n in raw.split(",") if n.strip()]


def get_account(name: str) -> AccountFingerprint:
    """Build an AccountFingerprint for one named account."""
    auth = _required(name)
    device_uuid = _with_fallback(f"{name}_DEVICE_UUID", "DEFAULT_DEVICE_UUID")
    device_name = _with_fallback(f"{name}_DEVICE_NAME", "DEFAULT_DEVICE_NAME")
    app_version = _with_fallback(f"{name}_APP_VERSION", "DEFAULT_APP_VERSION")
    numeric_id  = _with_fallback(f"{name}_NUMERIC_ID",  "DEFAULT_NUMERIC_ID") or ""

    missing = []
    if not device_uuid: missing.append("DEVICE_UUID")
    if not device_name: missing.append("DEVICE_NAME")
    if not app_version: missing.append("APP_VERSION")
    if missing:
        raise RuntimeError(
            f"Account {name} missing fingerprint field(s): {missing}. "
            f"Set per-account ({name}_DEVICE_UUID etc.) or DEFAULT_DEVICE_UUID etc."
        )

    return AccountFingerprint(
        name=name,
        auth_info=auth,
        device_uuid=device_uuid,
        device_name=device_name,
        app_version=app_version,
        numeric_id=numeric_id,
    )


def get_all_accounts() -> list[AccountFingerprint]:
    """All accounts declared in ACCOUNTS, built into fingerprints."""
    return [get_account(n) for n in list_account_names()]


if __name__ == "__main__":
    # Quick visibility — what does this .env give us?
    for name in list_account_names():
        try:
            fp = get_account(name)
            print(f"{name}: device={fp.device_name} v{fp.app_version} uuid={fp.device_uuid[:8]}…")
        except RuntimeError as e:
            print(f"{name}: ERROR — {e}")
