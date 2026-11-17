from datetime import timedelta

from meross_iot.http_api import _SECRET


_DB_PATH = '/data/database.db'
TOKEN_ABSOLUTE_TTL = timedelta(days=30)
TOKEN_IDLE_TTL = timedelta(days=7)
TOKEN_TOUCH_INTERVAL = timedelta(hours=1)
BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_USER_ID = 1
