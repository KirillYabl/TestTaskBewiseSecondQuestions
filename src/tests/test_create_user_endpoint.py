import fastapi.testclient

import server


def test_successful_user_creation():
    with fastapi.testclient.TestClient(server.app) as fastapi_client:
        params = {
            "user_name": "user1"
        }
        response = fastapi_client.post("/user", json=params)
        assert response.status_code == 200
        decoded_response = response.json()
        assert "user_id" in decoded_response
        assert "token" in decoded_response


def test_unsucessful_duplicate_user():
    with fastapi.testclient.TestClient(server.app) as fastapi_client:
        params = {
            "user_name": "user1"
        }
        response = fastapi_client.post("/user", json=params)
        assert response.status_code == 200

        response = fastapi_client.post("/user", json=params)
        assert response.status_code == 400
