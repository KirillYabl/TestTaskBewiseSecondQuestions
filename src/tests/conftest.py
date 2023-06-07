import fastapi.testclient
import pytest

import db_models
import server


def fastapi_client():
    with fastapi.testclient.TestClient(server.app) as client:
        yield client


@pytest.fixture
def db_session():
    return db_models.db.get_session()


@pytest.fixture(autouse=True)
def clear_database(db_session):
    db_session.query(db_models.User).delete()
    db_session.query(db_models.UserAudio).delete()
    db_session.commit()