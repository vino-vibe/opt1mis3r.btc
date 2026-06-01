"""
Shared client for opt1mis3r — handles auth header construction, sentry headers,
rate limiting with jitter, and a dry-run posture. Used by every script.

Why this exists separately from the friend's per-file build_headers():
  - Single source of truth for headers means a fingerprint tweak happens in one place.
  - Rate limiting belongs at the client layer, not duplicated inside each loop.
  - Dry-run is a posture flag, not something to bolt on later.
  - Sentry headers are sent by every iOS request — their absence is a strong
    signal we're not the iOS app.
"""
from __future__ import annotations

import os
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import requests

from token_generation import tokens

API_BASE_URL = "https://api.real.vg"

# Default cadence — overridable per Client instance.
DEFAULT_MIN_GAP_S = 4.0
DEFAULT_MAX_GAP_S = 8.5

# Named cadence profiles for different action classes. Use these instead of
# hand-tuning min_gap/max_gap per script — it keeps the rules in one place and
# explicit about what behavior each tier is impersonating.
#
# Ranges express total wait between any two outbound calls, in seconds.
CADENCE_OTD_CLAIM = (1.5, 4.0)   # batch-tappable in the iOS app — fast burst is realistic
CADENCE_WRITE     = (2.5, 6.0)   # pack buy, boost, list — each is a deliberate user action
CADENCE_READ      = (4.0, 8.5)   # default — no rush on reads, look like idle browsing

# Sentry constants — public_key is from the iOS app's embedded DSN and is
# safe to keep here (it's not a secret).
SENTRY_PUBLIC_KEY = "00e61a8109694360a8db52afe3f9a4fa"
SENTRY_ENVIRONMENT = "production"


@dataclass
class AccountFingerprint:
    """Everything we need to impersonate one iPhone-bound account."""
    name: str
    auth_info: str            # "<user_id>!<token>!<device_uuid>"
    device_uuid: str          # UPPERCASE iOS-style UUID (different from auth_info's uuid)
    device_name: str          # e.g. "iPhone15,3"
    app_version: str          # e.g. "32"
    numeric_id: str = ""      # numeric account ID used by /userpassboostercards inventory endpoint


def _sentry_pair() -> tuple[str, str]:
    """Fresh (trace_id, span_id) per call — 32 hex / 16 hex like the iOS app."""
    return uuid.uuid4().hex, uuid.uuid4().hex[:16]


class RateLimitedClient:
    """
    A requests-wrapping client that:
      * builds Real iOS API headers per call (fresh native+request token, fresh sentry pair)
      * enforces a minimum gap + jitter between any two outbound calls
      * supports dry-run (logs intended request, returns a fake 200)

    Posture: read by default. Pass `confirm_write=True` to any mutating call.
    """

    def __init__(
        self,
        fp: AccountFingerprint,
        *,
        min_gap_s: float = DEFAULT_MIN_GAP_S,
        max_gap_s: float = DEFAULT_MAX_GAP_S,
        dry_run: bool = False,
    ) -> None:
        self.fp = fp
        self.min_gap_s = min_gap_s
        self.max_gap_s = max_gap_s
        self.dry_run = dry_run
        self._last_call_at: float = 0.0
        self._session = requests.Session()

    # -- timing ------------------------------------------------------------------

    def _wait(self) -> None:
        """Sleep until min_gap_s + uniform jitter has elapsed since the last call."""
        now = time.monotonic()
        target_gap = random.uniform(self.min_gap_s, self.max_gap_s)
        elapsed = now - self._last_call_at
        if elapsed < target_gap:
            time.sleep(target_gap - elapsed)
        self._last_call_at = time.monotonic()

    # -- headers -----------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        native, req = tokens()
        trace_id, span_id = _sentry_pair()
        sentry_release = os.getenv("SENTRY_RELEASE", "vg.real-10.145")
        cf = os.getenv("USER_AGENT_CFNETWORK", "3860.400.51")
        darwin = os.getenv("USER_AGENT_DARWIN", "25.3.0")
        return {
            "Host": "api.real.vg",
            "real-device-uuid": self.fp.device_uuid,
            "real-device-name": self.fp.device_name,
            "real-version": self.fp.app_version,
            "real-device-type": "ios",
            "real-auth-info": self.fp.auth_info,
            "real-request-token": req,
            "real-native-request-token": native,
            # Sentry headers — every iOS request sends these.
            "sentry-trace": f"{trace_id}-{span_id}-0",
            "baggage": (
                f"sentry-environment={SENTRY_ENVIRONMENT},"
                f"sentry-public_key={SENTRY_PUBLIC_KEY},"
                f"sentry-release={sentry_release},"
                f"sentry-trace_id={trace_id}"
            ),
            "Accept": "application/json",
            "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": f"real/1 CFNetwork/{cf} Darwin/{darwin}",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
        }

    # -- verbs -------------------------------------------------------------------

    def get(self, path: str, params: Optional[dict] = None) -> requests.Response:
        return self._call("GET", path, params=params, json_body=None, is_write=False)

    def post(
        self, path: str, json_body: Optional[dict] = None, *, confirm_write: bool = False
    ) -> requests.Response:
        if not confirm_write:
            raise RuntimeError(
                f"Refusing POST {path} without confirm_write=True (write-posture safety)."
            )
        return self._call("POST", path, params=None, json_body=json_body, is_write=True)

    def put(
        self, path: str, json_body: Optional[dict] = None, *, confirm_write: bool = False
    ) -> requests.Response:
        if not confirm_write:
            raise RuntimeError(
                f"Refusing PUT {path} without confirm_write=True (write-posture safety)."
            )
        return self._call("PUT", path, params=None, json_body=json_body, is_write=True)

    # -- internals ---------------------------------------------------------------

    def _call(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict],
        json_body: Optional[dict],
        is_write: bool,
    ) -> requests.Response:
        url = f"{API_BASE_URL}{path}"
        self._wait()

        if self.dry_run and is_write:
            print(f"[DRY-RUN] {method} {url}  json={json_body}")
            return _FakeResponse(200, {"dry_run": True, "method": method, "url": url})

        resp = self._session.request(
            method=method,
            url=url,
            headers=self._headers(),
            params=params,
            json=json_body,
            timeout=15,
        )
        return resp


class _FakeResponse:
    """Stand-in for requests.Response when dry-running."""
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload
