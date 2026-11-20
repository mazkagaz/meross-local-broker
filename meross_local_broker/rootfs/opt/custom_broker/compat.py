# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0)
"""Local replacements for the few meross_iot symbols the broker used."""
from __future__ import annotations

from enum import IntEnum

MEROSS_SECRET = "23x17ahWarFH6w29"


class ErrorCodes(IntEnum):
    CODE_NO_ERROR = 0
    CODE_UNEXISTING_ACCOUNT = 1002
    CODE_TOKEN_ERROR = 1022
    CODE_WRONG_CREDENTIALS = 1004
    CODE_GENERIC_ERROR = 5000


class OnlineStatus(IntEnum):
    UNKNOWN = -1
    ONLINE = 1
    OFFLINE = 2


class HttpApiError(Exception):
    def __init__(self, error_code=ErrorCodes.CODE_GENERIC_ERROR) -> None:
        if isinstance(error_code, ErrorCodes):
            self.error_code = error_code
            message = error_code.name
        else:
            self.error_code = ErrorCodes.CODE_GENERIC_ERROR
            message = str(error_code)
        super().__init__(message)
