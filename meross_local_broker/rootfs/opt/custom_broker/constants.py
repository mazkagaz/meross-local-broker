# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
from datetime import timedelta

from compat import MEROSS_SECRET as _SECRET


_DB_PATH = '/data/database.db'
TOKEN_ABSOLUTE_TTL = timedelta(days=30)
TOKEN_IDLE_TTL = timedelta(days=7)
TOKEN_TOUCH_INTERVAL = timedelta(hours=1)
BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_USER_ID = 1
