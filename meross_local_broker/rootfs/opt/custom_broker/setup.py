from hashlib import md5
from uuid import uuid4

from logger import get_logger
import argparse
from constants import DEFAULT_USER_ID
from database import init_db
from db_helper import dbhelper
from model.db_models import User
from model.enums import EventType

l = get_logger("setup")


def setup_account(email: str, password: str) -> User:
    user_key = str(md5(uuid4().bytes).hexdigest().lower())
    user_id = DEFAULT_USER_ID

    # The broker applies the same salt+MD5+SHA256 scheme as the login
    # endpoints (db_helper.add_update_user).
    user = dbhelper.add_update_user(user_id=user_id, email=email, password=password, user_key=user_key)
    dbhelper.add_update_configuration(enable_meross_link=False, local_user_id=user.user_id)
    l.info("User %s configured", user.email)
    dbhelper.store_event(event_type=EventType.CONFIGURATION_CHANGE, details=f"Login username/password has been changed.")
    return user


def main():
    init_db()
   

if __name__ == '__main__':
    main()
