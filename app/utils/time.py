"""Time helpers.

datetime.utcnow() is deprecated (Python 3.12+) in favor of
datetime.now(timezone.utc), but every DateTime column in this codebase is
naive (no timezone=True), and naive/aware datetimes can't be compared or
subtracted without raising TypeError. Swapping call sites one-by-one to
datetime.now(timezone.utc) would produce aware datetimes that break those
comparisons and can be silently mangled by some DB drivers on insert.

utcnow() here returns the same naive-UTC value datetime.utcnow() did,
using the non-deprecated API under the hood, so it's a drop-in replacement.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now — safe drop-in replacement for datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
