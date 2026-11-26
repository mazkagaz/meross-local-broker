# Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
# Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from constants import _DB_PATH

dbpath = os.environ.get("DB_PATH")
if dbpath is None:
    dbpath = _DB_PATH

dbpath = f'sqlite:///{dbpath}'

engine = create_engine(dbpath)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


def add_password_upgraded_column():
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE users ADD password_upgraded Boolean DEFAULT 1'))
        conn.execute(text('UPDATE users SET password_upgraded=0'))


def migrate_user_tokens():
    """Drop the legacy plaintext-token table so every session is invalidated.

    Sessions are now stored as SHA-256 hashes with expiry metadata; old rows
    cannot be reused and must not survive the migration.
    """
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text('SELECT * FROM pragma_table_info("user_tokens")'))}
        replace_tokens = bool(columns and 'token_hash' not in columns)
        if replace_tokens:
            conn.execute(text('DROP TABLE IF EXISTS user_tokens'))
    if replace_tokens:
        from model.db_models import UserToken
        UserToken.__table__.create(bind=engine, checkfirst=True)


def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    Base.metadata.create_all(bind=engine)

    migrate_user_tokens()

    # Upgrade process.
    # Add the user.password_upgraded column
    with engine.begin() as conn:
        results = conn.execute(text('SELECT * FROM pragma_table_info("users") WHERE name = "password_upgraded"'))
        has_password_upgraded = len(list(results)) > 0
    if not has_password_upgraded:
        add_password_upgraded_column()
