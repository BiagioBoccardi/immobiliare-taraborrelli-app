import type { PropertyDetail } from "@taraborrelli/api-client";

import { features } from "./config";

type Photo = PropertyDetail["photos"][number];

/** Photos of a property that have the 3D version of their room (none while 3D is off). */
export function roomsWithThreeD(property: PropertyDetail): Photo[] {
  if (!features.threeD) return [];
  return property.photos.filter((photo) => Boolean(photo.three_d_url));
}

/** True when the property has something to show in 3D: rooms or a full model. */
export function hasThreeD(property: PropertyDetail): boolean {
  if (!features.threeD) return false;
  return Boolean(property.three_d_model) || roomsWithThreeD(property).length > 0;
}
