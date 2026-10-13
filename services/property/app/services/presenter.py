"""Turns models into API schemas, deciding what each audience is allowed to see."""

from decimal import ROUND_HALF_UP, Decimal

from app.models.property import Photo, Property
from app.schemas.property import (
    AdminPhotoOut,
    AdminPropertyOut,
    Coordinates,
    PhotoOut,
    PropertyCard,
    PropertyDetail,
    SoldCard,
)
from app.storage.base import MediaStorage

# Three decimals of a degree are about 100 meters.
APPROXIMATE = Decimal("0.001")


class Presenter:
    def __init__(self, storage: MediaStorage) -> None:
        self._storage = storage

    def photo(self, photo: Photo) -> PhotoOut:
        return PhotoOut(
            id=photo.id, url=self._storage.public_url(photo.storage_key), caption=photo.caption
        )

    def admin_photo(self, photo: Photo) -> AdminPhotoOut:
        return AdminPhotoOut(
            **self.photo(photo).model_dump(),
            position=photo.position,
            show_when_sold=photo.show_when_sold,
            content_type=photo.content_type,
            size_bytes=photo.size_bytes,
        )

    @staticmethod
    def coordinates(item: Property) -> Coordinates | None:
        if item.latitude is None or item.longitude is None:
            return None
        if item.show_exact_location:
            return Coordinates(latitude=item.latitude, longitude=item.longitude, exact=True)
        return Coordinates(
            latitude=item.latitude.quantize(APPROXIMATE, rounding=ROUND_HALF_UP),
            longitude=item.longitude.quantize(APPROXIMATE, rounding=ROUND_HALF_UP),
            exact=False,
        )

    def card(self, item: Property) -> PropertyCard:
        return PropertyCard(**self._card_fields(item))

    def detail(self, item: Property) -> PropertyDetail:
        return PropertyDetail(
            **self._card_fields(item),
            description=item.description,
            condominium_fees=item.condominium_fees,
            floor=item.floor,
            total_floors=item.total_floors,
            year_built=item.year_built,
            condition=item.condition,
            energy_class=item.energy_class,
            features=item.features,
            tenant_types=item.tenant_types,
            accommodation=item.accommodation,
            photos=[self.photo(photo) for photo in item.photos],
        )

    def sold(self, item: Property) -> SoldCard:
        return SoldCard(
            id=item.id,
            contract=item.contract,
            property_type=item.property_type,
            municipality=item.municipality,
            zone=item.zone,
            closed_on=item.closed_at.date() if item.closed_at else None,
            photos=[self.photo(photo) for photo in item.photos if photo.show_when_sold],
        )

    def admin(self, item: Property) -> AdminPropertyOut:
        data = {
            name: getattr(item, name)
            for name in AdminPropertyOut.model_fields
            if name not in {"photos", "reference"}
        }
        return AdminPropertyOut(
            **data,
            reference=item.reference,
            photos=[self.admin_photo(photo) for photo in item.photos],
        )

    def _card_fields(self, item: Property) -> dict[str, object]:
        return {
            "id": item.id,
            "reference": item.reference,
            "status": item.status,
            "contract": item.contract,
            "property_type": item.property_type,
            "title": item.title,
            "price": item.price,
            "municipality": item.municipality,
            "zone": item.zone,
            "surface_sqm": item.surface_sqm,
            "rooms": item.rooms,
            "bedrooms": item.bedrooms,
            "bathrooms": item.bathrooms,
            "is_featured": item.is_featured,
            "cover_photo": self.photo(item.photos[0]) if item.photos else None,
            "coordinates": self.coordinates(item),
            "available_from": item.available_from,
            "published_at": item.published_at,
        }
