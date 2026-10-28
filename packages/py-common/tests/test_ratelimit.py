from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from py_common.errors import register_error_handlers
from py_common.ratelimit import MAX_TRACKED_VISITORS, RateLimiter, rate_limit_dependency


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_rate_limiter_allows_up_to_the_limit_then_refuses() -> None:
    limiter = RateLimiter(limit=3, window_seconds=60, clock=FakeClock())

    results = [limiter.allow("1.2.3.4") for _ in range(4)]

    assert results == [True, True, True, False]


def test_rate_limiter_counts_each_visitor_separately() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=FakeClock())

    assert limiter.allow("1.1.1.1")
    assert limiter.allow("2.2.2.2")
    assert not limiter.allow("1.1.1.1")


def test_rate_limiter_allows_again_after_the_window() -> None:
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.allow("1.1.1.1")

    clock.now += 61

    assert limiter.allow("1.1.1.1")


def test_rate_limiter_forgets_the_oldest_visitors_beyond_the_cap() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=FakeClock())
    for n in range(MAX_TRACKED_VISITORS + 1):
        limiter.allow(f"visitor-{n}")

    assert limiter.allow("visitor-0")  # forgotten, so allowed again
    assert not limiter.allow(f"visitor-{MAX_TRACKED_VISITORS}")


def _app(enabled: bool, limit: int = 2) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    limiter = RateLimiter(limit, 60) if enabled else None
    check = rate_limit_dependency(lambda _request: limiter)

    @app.post("/form", dependencies=[Depends(check)])
    async def form(request: Request) -> dict[str, str]:
        return {"ok": "yes"}

    return TestClient(app)


def test_dependency_returns_429_with_uniform_error_over_the_limit() -> None:
    client = _app(enabled=True, limit=2)
    headers = {"x-nf-client-connection-ip": "5.6.7.8"}

    codes = [client.post("/form", headers=headers).status_code for _ in range(3)]
    response = client.post("/form", headers=headers)

    assert codes == [200, 200, 429]
    assert response.json()["code"] == "rate_limited"


def test_dependency_uses_the_netlify_then_forwarded_address() -> None:
    client = _app(enabled=True, limit=1)

    first = client.post("/form", headers={"x-nf-client-connection-ip": "9.9.9.9"})
    same_visitor = client.post("/form", headers={"x-forwarded-for": "9.9.9.9, 10.0.0.1"})
    other_visitor = client.post("/form", headers={"x-forwarded-for": "8.8.8.8, 10.0.0.1"})

    assert [first.status_code, same_visitor.status_code, other_visitor.status_code] == [
        200,
        429,
        200,
    ]


def test_dependency_does_nothing_when_disabled() -> None:
    client = _app(enabled=False, limit=1)

    codes = {client.post("/form").status_code for _ in range(5)}

    assert codes == {200}
