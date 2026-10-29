from fastapi import FastAPI
from fastapi.testclient import TestClient

from errors import register_error_handlers
from tests.test_events import assert_error


def test_unexpected_exception_returns_json_500():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise ValueError("internal detail")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert_error(response, 500, "INTERNAL_ERROR")
    assert "internal detail" not in response.text
