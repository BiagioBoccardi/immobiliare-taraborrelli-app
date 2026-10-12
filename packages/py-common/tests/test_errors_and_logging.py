import json
import logging

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from py_common.errors import NotFoundError, register_error_handlers
from py_common.health import health_router
from py_common.logging import (
    REQUEST_ID_HEADER,
    JsonFormatter,
    add_request_id_middleware,
    configure_logging,
    request_id_var,
)


class Payload(BaseModel):
    phone: str


def build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)
    add_request_id_middleware(app)
    app.include_router(health_router())

    @app.get("/missing")
    async def missing() -> None:
        raise NotFoundError(details={"id": "42"})

    @app.get("/teapot")
    async def teapot() -> None:
        raise HTTPException(status_code=405, detail="nope")

    @app.post("/echo")
    async def echo(payload: Payload) -> Payload:
        return payload

    return app


async def test_app_error_returns_uniform_format() -> None:
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://t") as c:
        response = await c.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "code": "not_found",
        "message": "Resource not found",
        "details": {"id": "42"},
    }


async def test_http_exception_returns_uniform_format() -> None:
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://t") as c:
        response = await c.get("/teapot")

    assert response.status_code == 405
    assert response.json() == {"code": "method_not_allowed", "message": "nope", "details": {}}


async def test_validation_error_does_not_echo_submitted_values() -> None:
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://t") as c:
        response = await c.post("/echo", json={"phone": 3331234567})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation_error"
    assert "3331234567" not in response.text
    assert body["details"]["errors"][0]["loc"] == ["body", "phone"]


async def test_health_propagates_request_id_header() -> None:
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://t") as c:
        response = await c.get("/health", headers={REQUEST_ID_HEADER: "abc123"})

    assert response.json() == {"status": "ok"}
    assert response.headers[REQUEST_ID_HEADER] == "abc123"


async def test_request_without_request_id_gets_generated_one() -> None:
    async with AsyncClient(transport=ASGITransport(app=build_app()), base_url="http://t") as c:
        response = await c.get("/health")

    assert len(response.headers[REQUEST_ID_HEADER]) == 32


def test_json_formatter_includes_request_id_and_service() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello", None, None)
    token = request_id_var.set("req-1")
    try:
        line = JsonFormatter("lead").format(record)
    finally:
        request_id_var.reset(token)

    data = json.loads(line)
    assert data["service"] == "lead"
    assert data["request_id"] == "req-1"
    assert data["message"] == "hello"


def test_configure_logging_routes_uvicorn_through_json_handler() -> None:
    logging.getLogger("uvicorn.access").addHandler(logging.NullHandler())

    configure_logging("lead", "warning")

    root = logging.getLogger()
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    assert root.level == logging.WARNING
    assert logging.getLogger("uvicorn.access").handlers == []
    assert logging.getLogger("uvicorn.access").propagate
