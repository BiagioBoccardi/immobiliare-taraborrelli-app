import type {
  Accommodation,
  AdminProperty,
  Contract,
  EnergyClass,
  Feature,
  PropertyCondition,
  PropertyCreate,
  PropertyStatus,
  PropertyType,
  TenantType,
} from "@taraborrelli/api-client";

import { t } from "../i18n";

export const CONTRACTS: Contract[] = ["sale", "rent"];
export const PROPERTY_TYPES: PropertyType[] = [
  "apartment",
  "house",
  "villa",
  "attic",
  "commercial",
  "land",
  "garage",
  "other",
];
export const CONDITIONS: PropertyCondition[] = ["new", "renovated", "good", "to_renovate"];
export const ENERGY_CLASSES: EnergyClass[] = ["A4", "A3", "A2", "A1", "B", "C", "D", "E", "F", "G"];
export const FEATURES: Feature[] = [
  "elevator",
  "parking",
  "garage",
  "garden",
  "terrace",
  "balcony",
  "cellar",
  "furnished",
  "air_conditioning",
  "autonomous_heating",
];
export const TENANT_TYPES: TenantType[] = ["students", "workers", "families"];
export const ACCOMMODATIONS: Accommodation[] = ["entire_property", "single_room", "shared_room"];
export const PROPERTY_STATUSES: PropertyStatus[] = [
  "draft",
  "published",
  "reserved",
  "sold",
  "rented",
  "archived",
];

/** Same rules as the property service: the panel only offers the allowed changes. */
export const STATUS_TRANSITIONS: Record<PropertyStatus, PropertyStatus[]> = {
  draft: ["published", "archived"],
  published: ["reserved", "sold", "rented", "draft", "archived"],
  reserved: ["published", "sold", "rented"],
  sold: ["archived"],
  rented: ["published", "archived"],
  archived: ["draft"],
};

/** Form values are kept as strings, as the inputs produce them. */
export interface PropertyFormState {
  contract: Contract;
  property_type: PropertyType;
  external_ref: string;
  title: string;
  description: string;
  price: string;
  condominium_fees: string;
  is_featured: boolean;
  surface_sqm: string;
  rooms: string;
  bedrooms: string;
  bathrooms: string;
  floor: string;
  total_floors: string;
  year_built: string;
  condition: PropertyCondition | "";
  energy_class: EnergyClass | "";
  features: Feature[];
  municipality: string;
  zone: string;
  address: string;
  latitude: string;
  longitude: string;
  show_exact_location: boolean;
  tenant_types: TenantType[];
  accommodation: Accommodation | "";
  available_from: string;
}

export const EMPTY_FORM: PropertyFormState = {
  contract: "sale",
  property_type: "apartment",
  external_ref: "",
  title: "",
  description: "",
  price: "",
  condominium_fees: "",
  is_featured: false,
  surface_sqm: "",
  rooms: "",
  bedrooms: "",
  bathrooms: "",
  floor: "",
  total_floors: "",
  year_built: "",
  condition: "",
  energy_class: "",
  features: [],
  municipality: "Chieti",
  zone: "",
  address: "",
  latitude: "",
  longitude: "",
  show_exact_location: false,
  tenant_types: [],
  accommodation: "",
  available_from: "",
};

const text = (value: string | number | null | undefined): string =>
  value === null || value === undefined ? "" : String(value);

export function formFromProperty(property: AdminProperty): PropertyFormState {
  return {
    contract: property.contract,
    property_type: property.property_type,
    external_ref: text(property.external_ref),
    title: property.title,
    description: property.description,
    price: text(property.price),
    condominium_fees: text(property.condominium_fees),
    is_featured: property.is_featured,
    surface_sqm: text(property.surface_sqm),
    rooms: text(property.rooms),
    bedrooms: text(property.bedrooms),
    bathrooms: text(property.bathrooms),
    floor: text(property.floor),
    total_floors: text(property.total_floors),
    year_built: text(property.year_built),
    condition: property.condition ?? "",
    energy_class: property.energy_class ?? "",
    features: property.features,
    municipality: property.municipality,
    zone: text(property.zone),
    address: text(property.address),
    latitude: text(property.latitude),
    longitude: text(property.longitude),
    show_exact_location: property.show_exact_location,
    tenant_types: property.tenant_types,
    accommodation: property.accommodation ?? "",
    available_from: text(property.available_from),
  };
}

const integer = (value: string): number | null => {
  const trimmed = value.trim();
  return trimmed === "" ? null : Number.parseInt(trimmed, 10);
};

const optionalText = (value: string): string | null => value.trim() || null;

/** Converts the form into the API payload. Rental fields are cleared for sales. */
export function payloadFromForm(form: PropertyFormState): PropertyCreate {
  const isRent = form.contract === "rent";
  return {
    contract: form.contract,
    property_type: form.property_type,
    external_ref: optionalText(form.external_ref),
    title: form.title.trim(),
    description: form.description.trim(),
    price: integer(form.price) ?? 0,
    condominium_fees: integer(form.condominium_fees),
    is_featured: form.is_featured,
    surface_sqm: integer(form.surface_sqm) ?? 0,
    rooms: integer(form.rooms),
    bedrooms: integer(form.bedrooms),
    bathrooms: integer(form.bathrooms),
    floor: integer(form.floor),
    total_floors: integer(form.total_floors),
    year_built: integer(form.year_built),
    condition: form.condition || null,
    energy_class: form.energy_class || null,
    features: form.features,
    municipality: form.municipality.trim(),
    zone: optionalText(form.zone),
    address: optionalText(form.address),
    latitude: optionalText(form.latitude.replace(",", ".")),
    longitude: optionalText(form.longitude.replace(",", ".")),
    show_exact_location: form.show_exact_location,
    tenant_types: isRent ? form.tenant_types : [],
    accommodation: isRent ? form.accommodation || null : null,
    available_from: isRent ? optionalText(form.available_from) : null,
  };
}

export type FormErrors = Partial<Record<keyof PropertyFormState, string>>;

/** Checks the required fields before calling the API; the service validates everything else. */
export function validateForm(form: PropertyFormState): FormErrors {
  const errors: FormErrors = {};
  const required = t("common.required");
  if (form.title.trim().length < 5) errors.title = required;
  if (form.price.trim() === "") errors.price = required;
  if (form.surface_sqm.trim() === "") errors.surface_sqm = required;
  if (form.municipality.trim().length < 2) errors.municipality = required;
  if ((form.latitude.trim() === "") !== (form.longitude.trim() === "")) {
    errors.longitude = required;
  }
  return errors;
}
