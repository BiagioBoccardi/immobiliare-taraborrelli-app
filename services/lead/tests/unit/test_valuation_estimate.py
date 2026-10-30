from datetime import UTC, datetime, timedelta

from py_common.events import InMemoryEventPublisher

from app.schemas.lead import ValuationCreate
from app.services.lead import LeadService
from app.services.listing_prices import ListingStats
from app.services.omi import OmiService, UploadedFile
from tests.factories import omi_kml, omi_values_csv, omi_zones_csv, valuation_payload
from tests.unit.fakes import FakeLeadRepository, FakeListingPrices, FakeOmiRepository

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
# Inside the fictional zone B1 of the test files.
IN_ZONE = {"latitude": 42.35, "longitude": 14.16, "address": "Via di Prova 1, Chieti"}
OUTSIDE = {"latitude": 41.0, "longitude": 13.0}
LISTINGS = ListingStats(
    scope="municipality_type", listings=5, low_per_sqm=1000, median_per_sqm=1200, high_per_sqm=1400
)


async def _service(
    listings: FakeListingPrices | None = None,
) -> tuple[LeadService, FakeLeadRepository]:
    omi = OmiService(FakeOmiRepository(), clock=lambda: NOW)
    await omi.import_files(
        UploadedFile("valori.csv", omi_values_csv()),
        UploadedFile("zone.csv", omi_zones_csv()),
        [UploadedFile("chieti.kml", omi_kml())],
    )
    repo = FakeLeadRepository()
    service = LeadService(
        repo,
        InMemoryEventPublisher(),
        timedelta(days=7),
        clock=lambda: NOW,
        omi=omi,
        listings=listings or FakeListingPrices(),
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


async def test_create_valuation_without_omi_nor_listings_has_no_estimate() -> None:
    service, repo = await _service()

    created = await service.create_valuation(ValuationCreate.model_validate(valuation_payload()))

    assert (created.estimate, created.estimate_unavailable) == (None, "no_data")
    assert repo.leads[created.lead.id].details == {}


async def test_create_valuation_outside_the_zones_is_still_a_lead() -> None:
    service, repo = await _service()
    data = ValuationCreate.model_validate(valuation_payload(**OUTSIDE))

    created = await service.create_valuation(data)

    assert created.estimate_unavailable == "no_data"
    assert created.lead.id in repo.leads


async def test_create_valuation_outside_the_zones_uses_the_agency_listings() -> None:
    listings = FakeListingPrices(LISTINGS)
    service, repo = await _service(listings)
    data = ValuationCreate.model_validate(valuation_payload(surface_sqm=95, **OUTSIDE))

    created = await service.create_valuation(data)

    estimate = created.estimate
    assert estimate is not None
    assert estimate.basis == "agency_listings"
    # Asking prices lowered by 8%: 1000-1400 €/m² become 920-1288 €/m².
    assert (estimate.min_per_sqm, estimate.max_per_sqm) == (920, 1288)
    assert (estimate.min_value, estimate.max_value) == (87_000, 123_000)
    assert (estimate.listings, estimate.listings_scope) == (5, "municipality_type")
    assert estimate.source == "Immobili in vendita di Immobiliare Taraborrelli"
    assert listings.calls == [("Chieti", "apartment")]
    assert repo.leads[created.lead.id].details["estimate"]["basis"] == "agency_listings"


async def test_create_valuation_without_position_uses_the_agency_listings() -> None:
    service, _ = await _service(FakeListingPrices(LISTINGS))

    created = await service.create_valuation(ValuationCreate.model_validate(valuation_payload()))

    assert created.estimate is not None and created.estimate.basis == "agency_listings"


async def test_create_valuation_in_an_omi_zone_does_not_ask_the_listings() -> None:
    listings = FakeListingPrices(LISTINGS)
    service, _ = await _service(listings)
    data = ValuationCreate.model_validate(valuation_payload(**IN_ZONE))

    created = await service.create_valuation(data)

    assert created.estimate is not None and created.estimate.basis == "omi"
    assert listings.calls == []


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

    assert (created.estimate, created.estimate_unavailable) == (None, "no_data")
