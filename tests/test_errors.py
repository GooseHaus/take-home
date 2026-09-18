from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError, TickerNotFound
from app.main import handle_app_error


def test_app_errors_become_structured_http_responses():
    app = FastAPI()
    app.add_exception_handler(AppError, handle_app_error)

    @app.get("/boom")
    def boom():
        raise TickerNotFound("No price data for 'NOPE'")

    response = TestClient(app).get("/boom")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "ticker_not_found", "message": "No price data for 'NOPE'"}}
