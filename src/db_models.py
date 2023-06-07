import enum
import logging
import os
import time
import uuid

import sqlalchemy.orm
import sqlalchemy.exc
import sqlalchemy.dialects.postgresql
import sqlalchemy_file.storage
import sqlalchemy_utils.types.choice
import libcloud.storage.drivers.local

import data_models

logger = logging.getLogger(__name__)
db_string = data_models.settings.db_string

stime = time.time()
warning_seconds = 60
while True:
    try:
        logger.debug("trying connect to db...")
        engine = sqlalchemy.create_engine(db_string, pool_pre_ping=True)
        engine.connect()
        break
    except sqlalchemy.exc.OperationalError:
        time.sleep(0.1)
        if time.time() - stime > warning_seconds:
            logger.warning(f"can't connect for {warning_seconds} seconds (db_string={db_string})")
            stime = time.time()

SessionLocal = sqlalchemy.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
base = sqlalchemy.orm.declarative_base()


class Database:
    def __init__(self):
        self._session = SessionLocal()

    def get_session(self) -> sqlalchemy.orm.Session:
        return self._session


db = Database()

os.makedirs(
    os.path.join(data_models.settings.storage_path, data_models.settings.storage_container_name),
    exist_ok=True
)
container = libcloud.storage.drivers.local.LocalStorageDriver(
    data_models.settings.storage_path
).get_container(data_models.settings.storage_container_name)
sqlalchemy_file.storage.StorageManager.add_storage("default", container)


def get_session():
    try:
        db_session = db.get_session()
        yield db_session
    finally:
        db_session.close()


class User(base):
    __tablename__ = 'User'

    user_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.Sequence("user_id_seq", start=1),
        primary_key=True
    )
    user_name = sqlalchemy.Column(sqlalchemy.String(250), nullable=False, unique=True)
    token = sqlalchemy.Column(
        sqlalchemy.String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4())
    )


class UserAudio(base):
    """Table for saving user audio, no need to use M2M cause one audio can't be used for many users"""

    class ConvertStatus(enum.Enum):
        pending = "pending"
        converting = "converting"
        finished = "finished"
        error = "error"
        not_valid = "not_valid"

    __tablename__ = 'UserAudio'

    audio_id = sqlalchemy.Column(
        sqlalchemy.String(36),
        default=lambda: str(uuid.uuid4()),
        primary_key=True
    )
    # file = sqlalchemy.Column(depot.fields.sqlalchemy.UploadedFileField())
    file = sqlalchemy.Column(sqlalchemy_file.FileField)
    user_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        nullable=False,
        index=True,
    )
    convert_status = sqlalchemy.Column(
        sqlalchemy_utils.types.choice.ChoiceType(ConvertStatus),
        nullable=False,
        index=True,
        default='pending',
    )


if __name__ == '__main__':
    base.metadata.create_all(engine, checkfirst=True)  # checkfirst=True - Explicit is better than implicit.
    logger.info("db created successfully")
