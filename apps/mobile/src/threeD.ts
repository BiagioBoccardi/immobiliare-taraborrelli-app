import type { PropertyDetail } from "@taraborrelli/api-client";

type Photo = PropertyDetail["photos"][number];

/** Photos of a property that have the 3D version of their room. */
export function roomsWithThreeD(property: PropertyDetail): Photo[] {
  return property.photos.filter((photo) => Boolean(photo.three_d_url));
}

/** True when the property has something to show in 3D: rooms or a full model. */
export function hasThreeD(property: PropertyDetail): boolean {
  return Boolean(property.three_d_model) || roomsWithThreeD(property).length > 0;
}
