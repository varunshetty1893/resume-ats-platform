"""Security utilities: Rate limiting, failed login tracking with exponential backoff, and input sanitization."""

import time
import re
from collections import defaultdict
from flask import request, current_app, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Global limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
    strategy="moving-window",
    headers_enabled=True,
)


class FailedLoginTracker:
    """Tracks failed authentication attempts per (IP, identifier) and computes

    exponential backoff delay and temporary lockouts without permanent hard lockouts.
    """

    def __init__(self):
        # key: str -> list of timestamps
        self._ip_attempts = defaultdict(list)
        self._account_attempts = defaultdict(list)
        self._window_seconds = 900  # 15 minute sliding window

    def _cleanup(self, attempts_list, now):
        cutoff = now - self._window_seconds
        return [ts for ts in attempts_list if ts > cutoff]

    def record_failure(self, ip: str, email: str = ""):
        now = time.time()
        ip_key = (ip or "").strip()
        email_key = (email or "").strip().lower()

        if ip_key:
            self._ip_attempts[ip_key] = self._cleanup(self._ip_attempts[ip_key], now)
            self._ip_attempts[ip_key].append(now)

        if email_key:
            self._account_attempts[email_key] = self._cleanup(self._account_attempts[email_key], now)
            self._account_attempts[email_key].append(now)

    def record_success(self, ip: str, email: str = ""):
        ip_key = (ip or "").strip()
        email_key = (email or "").strip().lower()
        if ip_key in self._ip_attempts:
            del self._ip_attempts[ip_key]
        if email_key in self._account_attempts:
            del self._account_attempts[email_key]

    def get_backoff_info(self, ip: str, email: str = "") -> dict:
        """Calculate required backoff delay (in seconds) based on failed attempt counts.

        Exponential backoff:
        1-2 failures: 0s
        3 failures: 2s
        4 failures: 4s
        5 failures: 8s
        6 failures: 16s
        7+ failures: 30s max cooldown per attempt
        """
        now = time.time()
        ip_key = (ip or "").strip()
        email_key = (email or "").strip().lower()

        ip_fails = len(self._cleanup(self._ip_attempts[ip_key], now)) if ip_key else 0
        account_fails = len(self._cleanup(self._account_attempts[email_key], now)) if email_key else 0
        max_fails = max(ip_fails, account_fails)

        if max_fails < 3:
            delay = 0
        elif max_fails == 3:
            delay = 2
        elif max_fails == 4:
            delay = 4
        elif max_fails == 5:
            delay = 8
        elif max_fails == 6:
            delay = 16
        else:
            delay = 30

        # Check last attempt time for active cooldown
        last_ts = 0
        if ip_key and self._ip_attempts[ip_key]:
            last_ts = max(last_ts, self._ip_attempts[ip_key][-1])
        if email_key and self._account_attempts[email_key]:
            last_ts = max(last_ts, self._account_attempts[email_key][-1])

        remaining_cooldown = 0
        if delay > 0 and last_ts > 0:
            elapsed = now - last_ts
            if elapsed < delay:
                remaining_cooldown = int(delay - elapsed) + 1

        return {
            "failed_attempts": max_fails,
            "required_delay": delay,
            "remaining_cooldown": remaining_cooldown,
            "is_throttled": remaining_cooldown > 0,
        }


# Singleton tracker
login_tracker = FailedLoginTracker()


def get_user_rate_limit_key():
    """Rate limit key combining authenticated user ID or remote IP."""
    from flask_login import current_user
    if current_user and current_user.is_authenticated:
        return f"user:{current_user.id}"
    return get_remote_address()
