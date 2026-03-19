"""Provider API key failover/rotation for tau2-bench LLM calls."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

import httpx


def _split_keys(raw: str) -> list[str]:
    return [k.strip() for k in (raw or "").split(",") if k and k.strip()]


def _uniq_preserve_order(keys: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for k in keys:
        if k not in seen:
            out.append(k)
            seen.add(k)
    return out


def _status_code_from_exception(e: BaseException) -> Optional[int]:
    status_code = getattr(e, "status_code", None)
    if status_code is not None:
        return status_code
    resp = getattr(e, "response", None)
    return getattr(resp, "status_code", None)


def is_transient_error(e: BaseException) -> bool:
    if isinstance(
        e, (TimeoutError, httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)
    ):
        return True
    if isinstance(e, OSError):
        return True

    name = type(e).__name__.lower()
    if "timeout" in name or "timedout" in name:
        return True
    if "serviceunavailable" in name:
        return True
    if "ratelimit" in name:
        return True

    status_code = _status_code_from_exception(e)
    if isinstance(status_code, int) and (status_code == 429 or 500 <= status_code <= 599):
        return True

    msg = str(e).lower()
    if "timeout" in msg or "timed out" in msg:
        return True
    if "rate limit" in msg or "too many requests" in msg:
        return True
    if "service unavailable" in msg or "bad gateway" in msg or "gateway timeout" in msg:
        return True
    return False


@dataclass
class KeyPool:
    keys: Sequence[str]
    cooldown_s: float = 30.0
    _unhealthy_until: dict[str, float] = None  # type: ignore[assignment]
    _active_key: str | None = None

    def __post_init__(self) -> None:
        self.keys = tuple(k.strip() for k in self.keys if k and k.strip())
        if not self.keys:
            raise ValueError("KeyPool requires at least one key.")
        self._unhealthy_until = {}
        # Start with primary key.
        self._active_key = self.keys[0]

    def _healthy(self, key: str, now: float) -> bool:
        return self._unhealthy_until.get(key, 0.0) <= now

    def choose(self) -> str:
        """Sticky selection:
        - keep using current active key while healthy
        - if active non-primary fails, switch back to primary
        - if primary fails, switch to a healthy alternate
        """
        now = time.time()
        primary = self.keys[0]

        if self._active_key and self._healthy(self._active_key, now):
            return self._active_key

        # If active is unhealthy, try primary first.
        if self._healthy(primary, now):
            self._active_key = primary
            return primary

        # Primary unhealthy: fail over to first healthy alternate.
        for k in self.keys[1:]:
            if self._healthy(k, now):
                self._active_key = k
                return k

        # If everything appears unhealthy, keep primary as default fallback.
        self._active_key = primary
        return primary

    def mark_unhealthy(self, key: str) -> None:
        self._unhealthy_until[key] = time.time() + float(self.cooldown_s)
        primary = self.keys[0]
        # If a non-primary key fails, prefer switching back to primary.
        if key != primary:
            self._active_key = primary
            return

        # Primary failed: choose the first healthy alternate as active.
        now = time.time()
        for k in self.keys[1:]:
            if self._healthy(k, now):
                self._active_key = k
                return


def key_pool_from_env(
    *,
    primary_env: str,
    pool_envs: Sequence[str],
    fallback_primary_envs: Sequence[str] = (),
    cooldown_env: str,
    default_cooldown_s: float = 30.0,
) -> Optional[KeyPool]:
    primary = (os.environ.get(primary_env) or "").strip()
    if not primary:
        for env in fallback_primary_envs:
            primary = (os.environ.get(env) or "").strip()
            if primary:
                break

    alternates: list[str] = []
    for env in pool_envs:
        alternates.extend(_split_keys(os.environ.get(env, "")))

    keys = _uniq_preserve_order(([primary] if primary else []) + alternates)
    if not keys:
        return None

    cooldown_raw = (os.environ.get(cooldown_env) or "").strip()
    try:
        cooldown_s = float(cooldown_raw) if cooldown_raw else default_cooldown_s
    except ValueError:
        cooldown_s = default_cooldown_s
    return KeyPool(keys=keys, cooldown_s=cooldown_s)

