from datetime import UTC, datetime, timedelta

from py_common.events import InMemoryEventPublisher

from app.schemas.lead import ValuationCreate
from app.services.lead import LeadService
from app.services.omi import OmiService, UploadedFile
from tests.factories import omi_kml, omi_values_csv, omi_zones_csv, valuation_payload
from tests.unit.fakes import FakeLeadRepository, FakeOmiRepository

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
# Inside the fictional zone B1 of the test files.
IN_ZONE = {"latitude": 42.35, "longitude": 14.16, "address": "Via di Prova 1, Chieti"}


async def _service() -> tuple[LeadService, FakeLeadRepository]:
    omi = OmiService(FakeOmiRepository(), clock=lambda: NOW)
    await omi.import_files(
        UploadedFile("valori.csv", omi_values_csv()),
        UploadedFile("zone.csv", omi_zones_csv()),
        [UploadedFile("chieti.kml", omi_kml())],
    )
    repo = FakeLeadRepository()
    service = LeadService(
        repo, InMemoryEventPublisher(), timedelta(days=7), clock=lambda: NOW, omi=omi
    )
    return service, repo


async def test_create_valuation_with_position_returns_estimate_of_the_zone() -> None:
    service, _ = await _service()
    data = ValuationCreate.model_validate(
        valuation_payload(cadastral_category="A2", surface_sqm=100, **IN_ZONE)
    )

    created = await service.create_valuation(data)

    assert created.estimate is not None
    assert (created.estimate.min_value, created.estimate.max_value) == (110_000, 150_000)
    assert (created.estimate.zone_code, created.estimate.zone_description) == (
        "B1",
        "CENTRO STORICO",
    )
    assert created.estimate.semester == "2026/1"
    assert created.estimate_unavailable is None


async def test_create_valuation_keeps_answers_and_estimate_in_the_lead() -> None:
    service, repo = await _service()
    data = ValuationCreate.model_validate(
        valuation_payload(building_works="yes", floor=2, has_elevator=True, **IN_ZONE)
    )

    created = await service.create_valuation(data)

    details = repo.leads[created.lead.id].details
    assert details["address"] == "Via di Prova 1, Chieti"
    assert (details["building_works"], details["floor"], details["has_elevator"]) == (
        "yes",
        2,
        True,
    )
    assert details["estimate"]["min_value"] == created.estimate.min_value  # type: ignore[union-attr]
    assert details["estimate"]["source"] == "OMI - Agenzia delle Entrate"


async def test_create_valuation_without_position_has_no_estimate() -> None:
    service, repo = await _service()

    created = await service.create_valuation(ValuationCreate.model_validate(valuation_payload()))

    assert (created.estimate, created.estimate_unavailable) == (None, "no_location")
    assert repo.leads[created.lead.id].details == {}


async def test_create_valuation_outside_the_zones_is_still_a_lead() -> None:
    service, repo = await _service()
    data = ValuationCreate.model_validate(valuation_payload(latitude=41.0, longitude=13.0))

    created = await service.create_valuation(data)

    assert created.estimate_unavailable == "outside_zones"
    assert created.lead.id in repo.leads


async def test_create_valuation_of_land_is_not_estimated() -> None:
    service, _ = await _service()
    data = ValuationCreate.model_validate(valuation_payload(property_type="land", **IN_ZONE))

    created = await service.create_valuation(data)

    assert created.estimate_unavailable == "type_not_supported"


async def test_create_valuation_of_villino_without_villa_quotes_uses_civil_homes() -> None:
    service, _ = await _service()
    # Zone D1 of the test files has only civil homes.
    data = ValuationCreate.model_validate(
        valuation_payload(cadastral_category="A7", latitude=42.35, longitude=14.18)
    )

    created = await service.create_valuation(data)

    assert created.estimate is not None
    assert created.estimate.zone_code == "D1"


async def test_create_valuation_without_quotation_for_the_type_reports_it() -> None:
    omi = OmiService(FakeOmiRepository(), clock=lambda: NOW)
    await omi.import_files(
        UploadedFile(
            "valori.csv",
            omi_values_csv([("B1", "Ville e Villini", "NORMALE", "P", "1300", "1800")]),
        ),
        None,
        [UploadedFile("chieti.kml", omi_kml())],
    )
    service = LeadService(
        FakeLeadRepository(), InMemoryEventPublisher(), timedelta(days=7), omi=omi
    )
    data = ValuationCreate.model_validate(valuation_payload(cadastral_category="A3", **IN_ZONE))

    created = await service.create_valuation(data)

    assert (created.estimate, created.estimate_unavailable) == (None, "no_quotes")
