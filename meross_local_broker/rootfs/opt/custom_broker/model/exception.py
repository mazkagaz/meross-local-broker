# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
class BadRequestError(Exception):
    def __init__(self, msg: str = None):
        self.msg = msg


class TokenError(Exception):
    """Invalid or expired session token."""

    def __init__(self, info: str = "token_invalid"):
        self.info = info


class RateLimitError(Exception):
    """Too many failed login attempts."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after


