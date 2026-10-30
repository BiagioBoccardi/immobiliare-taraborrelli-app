import json

import httpx
import pytest

from app.services.geocoding import GeocodingUnavailableError, NominatimGeocoder

RESULT = [
    {
        "lat": "42.3510",
        "lon": "14.1675",
        "display_name": "12, Via Arniense, Chieti, Abruzzo, 66100, Italia",
        "address": {
            "house_number": "12",
            "road": "Via Arniense",
            "city": "Chieti",
            "postcode": "66100",
        },
    },
    {"lat": "42.36", "lon": "14.14", "display_name": "Chieti Scalo, Chieti", "address": {}},
]


class Recorder:
    def __init__(self, status: int = 200, body: object = RESULT) -> None:
        self.requests: list[httpx.Request] = []
        self.status = status
        self.body = body

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, content=json.dumps(self.body).encode())


class FakeTime:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _geocoder(recorder: Recorder, time: FakeTime | None = None) -> NominatimGeocoder:
    time = time or FakeTime()
    return NominatimGeocoder(
        "https://nominatim.test",
        "TestAgent/1.0",
        email="agenzia@example.com",
        viewbox="13.85,42.55,14.80,41.65",
        transport=httpx.MockTransport(recorder),
        clock=time.clock,
        sleep=time.sleep,
    )


async def test_search_returns_places_with_short_labels() -> None:
    places = await _geocoder(Recorder()).search("via arniense 12 chieti")

    assert [p.label for p in places] == ["Via Arniense 12, Chieti", "Chieti Scalo, Chieti"]
    assert (places[0].latitude, places[0].longitude) == (42.351, 14.1675)
    assert (places[0].municipality, places[0].postcode) == ("Chieti", "66100")


async def test_search_sends_identification_and_area_preference() -> None:
    recorder = Recorder()

    await _geocoder(recorder).search("via arniense 12 chieti")

    request = recorder.requests[0]
    assert request.headers["User-Agent"] == "TestAgent/1.0"
    assert request.url.params["countrycodes"] == "it"
    assert request.url.params["viewbox"] == "13.85,42.55,14.80,41.65"
    assert request.url.params["email"] == "agenzia@example.com"


async def test_search_of_the_same_address_uses_the_cache() -> None:
    recorder = Recorder()
    geocoder = _geocoder(recorder)

    await geocoder.search("Via Arniense 12 Chieti")
    await geocoder.search("  via arniense   12 chieti ")

    assert len(recorder.requests) == 1


async def test_search_waits_one_second_between_requests() -> None:
    time = FakeTime()
    geocoder = _geocoder(Recorder(), time)

    await geocoder.search("via arniense chieti")
    time.now += 0.3
    await geocoder.search("corso marrucino chieti")

    assert time.slept == [pytest.approx(0.7)]


@pytest.mark.parametrize(("status", "body"), [(503, {}), (200, {"error": "x"}), (200, [{}])])
async def test_search_failure_raises_unavailable(status: int, body: object) -> None:
    with pytest.raises(GeocodingUnavailableError):
        await _geocoder(Recorder(status, body)).search("via arniense chieti")


async def test_search_does_not_log_the_address(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")

    await _geocoder(Recorder()).search("via arniense 12 chieti")

    assert "arniense" not in caplog.text
