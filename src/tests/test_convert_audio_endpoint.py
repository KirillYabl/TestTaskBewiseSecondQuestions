import contextlib
import os

import fastapi.testclient

import server
import db_models


def test_successful_upload_audio(db_session):
    with fastapi.testclient.TestClient(server.app) as fastapi_client:
        params = {
            "user_name": "user1"
        }
        response = fastapi_client.post("/user", json=params)
        assert response.status_code == 200
        decoded_response = response.json()

        try:
            with open("bad_audio", "wb+") as f:
                f.write(b"something")
                files = {"audio": f}
                response = fastapi_client.post("/record", params=decoded_response, files=files)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.remove("bad_audio")

        assert response.status_code == 200
        user_id = decoded_response["user_id"]
        audio_id = db_session.query(db_models.UserAudio).filter(
            db_models.UserAudio.convert_status == db_models.UserAudio.ConvertStatus.pending.value
        ).first().audio_id
        assert response.text == f"http://testserver/record?id={audio_id}&user_id={user_id}"


def test_wrong_user_token(db_session):
    with fastapi.testclient.TestClient(server.app) as fastapi_client:
        params = {
            "user_name": "user1"
        }
        response = fastapi_client.post("/user", json=params)
        assert response.status_code == 200
        decoded_response = response.json()
        decoded_response["token"] = "0"

        try:
            with open("bad_audio", "wb+") as f:
                f.write(b"something")
                files = {"audio": f}
                response = fastapi_client.post("/record", params=decoded_response, files=files)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.remove("bad_audio")

        assert response.status_code == 400