import contextlib
import os
import time

import fastapi.testclient

import db_models
import pydub
import server
import scheduler


def test_getting_bad_audio(db_session):
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

        get_record_url = response.text
        response = fastapi_client.get(get_record_url)
        assert response.status_code == 423
        assert "status=pending" in response.text

        scheduler.convert_audios()
        response = fastapi_client.get(get_record_url)
        assert response.status_code == 400


def test_successful_convertation(db_session):
    with fastapi.testclient.TestClient(server.app) as fastapi_client:
        params = {
            "user_name": "user1"
        }
        response = fastapi_client.post("/user", json=params)
        assert response.status_code == 200
        decoded_response = response.json()

        with open("/src/tests/valid_wav.wav", "rb") as f:
            files = {"audio": f}
            response = fastapi_client.post("/record", params=decoded_response, files=files)

        assert response.status_code == 200

        get_record_url = response.text
        response = fastapi_client.get(get_record_url)
        assert response.status_code == 423
        assert "status=pending" in response.text

        scheduler.convert_audios()
        response = fastapi_client.get(get_record_url)
        assert response.status_code == 200

        with open("/src/tests/valid_mp3.mp3", "wb") as f:
            f.write(response.content)

        pydub.AudioSegment.from_mp3("/src/tests/valid_mp3.mp3")

        with contextlib.suppress(FileNotFoundError):
            os.remove("/src/tests/valid_mp3.mp3")
