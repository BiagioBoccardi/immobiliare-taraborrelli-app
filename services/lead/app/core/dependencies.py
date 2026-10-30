from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated, cast

from fastapi import Depends, Request
from py_common.events import EventPublisher
from py_common.ratelimit import RateLimiter, rate_limit_dependency
from py_common.security import (
    TokenVerifier,
    build_auth_dependencies,
    build_optional_user_dependency,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.repositories.lead import SqlLeadRepository
from app.repositories.omi import SqlOmiRepository
from app.services.geocoding import Geocoder
from app.services.lead import LeadService
from app.services.listing_prices import ListingPrices
from app.services.notifications import StaffNotifier
from app.services.omi import OmiService


def get_settings_dep(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as session:
        yield session


def get_publisher(request: Request) -> EventPublisher:
    return cast(EventPublisher, request.app.state.publisher)


def get_token_verifier(request: Request) -> TokenVerifier:
    return cast(TokenVerifier, request.app.state.token_verifier)


def get_omi_service(session: Annotated[AsyncSession, Depends(get_session)]) -> OmiService:
    return OmiService(SqlOmiRepository(session))


def get_staff_notifier(request: Request) -> StaffNotifier:
    return cast(StaffNotifier, request.app.state.staff_notifier)


def get_listing_prices(request: Request) -> ListingPrices:
    return cast(ListingPrices, request.app.state.listing_prices)


def get_lead_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    publisher: Annotated[EventPublisher, Depends(get_publisher)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    omi: Annotated[OmiService, Depends(get_omi_service)],
    notifier: Annotated[StaffNotifier, Depends(get_staff_notifier)],
    listings: Annotated[ListingPrices, Depends(get_listing_prices)],
) -> LeadService:
    return LeadService(
        SqlLeadRepository(session),
        publisher,
        completion_window=timedelta(days=settings.valuation_completion_window_days),
        omi=omi,
        listings=listings,
        notifier=notifier,
    )


def get_geocoder(request: Request) -> Geocoder:
    # One instance per process: it keeps the cache and the one-request-per-second pace.
    return cast(Geocoder, request.app.state.geocoder)


require_user, require_staff = build_auth_dependencies(get_token_verifier)
optional_user = build_optional_user_dependency(get_token_verifier)


def _forms_limiter(request: Request) -> RateLimiter | None:
    return cast(RateLimiter | None, request.app.state.forms_limiter)


# Public forms: a person sends a few requests, not dozens (same limit as the gateway).
forms_rate_limit = rate_limit_dependency(_forms_limiter)
