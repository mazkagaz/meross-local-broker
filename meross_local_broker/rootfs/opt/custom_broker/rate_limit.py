"""Thread-safe in-process login rate limiting."""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

IP_WINDOW_SECONDS = 60
IP_MAX_FAILURES = 5
ACCOUNT_FREE_FAILURES = 5
ACCOUNT_BASE_BLOCK_SECONDS = 30
ACCOUNT_MAX_BLOCK_SECONDS = 900
PRUNE_INTERVAL_SECONDS = 60


class LoginRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._ip_failures: Dict[str, Deque[float]] = defaultdict(deque)
        self._account_failures: Dict[str, int] = defaultdict(int)
        self._account_last_failure: Dict[str, float] = {}
        self._account_blocked_until: Dict[str, float] = {}
        self._last_prune = 0.0

    @staticmethod
    def _account_key(account: str) -> str:
        return (account or "").strip().lower()

    def check(self, ip: str, account: str) -> Optional[int]:
        """Returns the remaining block in seconds, or None when allowed."""
        now = time.monotonic()
        account_key = self._account_key(account)
        with self._lock:
            self._prune(now)
            blocked_until = self._account_blocked_until.get(account_key)
            if blocked_until is not None and blocked_until > now:
                return max(1, int(blocked_until - now))
            failures = self._ip_failures.get(ip)
            if failures:
                while failures and failures[0] <= now - IP_WINDOW_SECONDS:
                    failures.popleft()
                if len(failures) >= IP_MAX_FAILURES:
                    return max(1, int(failures[0] + IP_WINDOW_SECONDS - now))
        return None

    def record_failure(self, ip: str, account: str) -> None:
        now = time.monotonic()
        account_key = self._account_key(account)
        with self._lock:
            self._ip_failures[ip].append(now)
            count = self._account_failures.get(account_key, 0) + 1
            self._account_failures[account_key] = count
            self._account_last_failure[account_key] = now
            if count >= ACCOUNT_FREE_FAILURES:
                exponent = min(count - ACCOUNT_FREE_FAILURES, 5)
                delay = min(ACCOUNT_BASE_BLOCK_SECONDS * (2 ** exponent),
                            ACCOUNT_MAX_BLOCK_SECONDS)
                self._account_blocked_until[account_key] = now + delay

    def clear(self, ip: str, account: str) -> None:
        account_key = self._account_key(account)
        with self._lock:
            self._ip_failures.pop(ip, None)
            self._account_failures.pop(account_key, None)
            self._account_last_failure.pop(account_key, None)
            self._account_blocked_until.pop(account_key, None)

    def reset(self) -> None:
        with self._lock:
            self._ip_failures.clear()
            self._account_failures.clear()
            self._account_last_failure.clear()
            self._account_blocked_until.clear()
            self._last_prune = 0.0

    def _prune(self, now: float) -> None:
        if now - self._last_prune < PRUNE_INTERVAL_SECONDS:
            return
        self._last_prune = now
        for ip in list(self._ip_failures):
            failures = self._ip_failures[ip]
            while failures and failures[0] <= now - IP_WINDOW_SECONDS:
                failures.popleft()
            if not failures:
                self._ip_failures.pop(ip, None)
        for account in list(self._account_failures):
            last = self._account_last_failure.get(account, 0)
            blocked = self._account_blocked_until.get(account, 0)
            if blocked <= now and last <= now - ACCOUNT_MAX_BLOCK_SECONDS:
                self._account_failures.pop(account, None)
                self._account_last_failure.pop(account, None)
                self._account_blocked_until.pop(account, None)


login_rate_limiter = LoginRateLimiter()
