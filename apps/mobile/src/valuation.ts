import type {
  BuildingWorks,
  CadastralCategory,
  LeadPropertyCondition,
  OwnerIntention,
  Place,
  ValuationCreate,
} from "@taraborrelli/api-client";

import { privacy } from "./config";
import { t } from "./i18n";

/** Homes the online estimate works for; other properties use the "Vendi casa" form. */
export type HomeType = "apartment" | "attic" | "house" | "villa";

export const HOME_TYPES: HomeType[] = ["apartment", "house", "villa", "attic"];
export const CADASTRAL_CATEGORIES: CadastralCategory[] = [
  "A2",
  "A3",
  "A4",
  "A7",
  "A8",
  "A1",
  "unknown",
];
export const CONDITIONS: LeadPropertyCondition[] = ["to_renovate", "good", "renovated", "new"];
export const WORKS: BuildingWorks[] = ["yes", "no", "unknown"];
export const INTENTIONS: OwnerIntention[] = ["know_value", "planning", "decided"];
/** -1 basement, 0 ground floor, 5 means "5th or higher". */
export const FLOORS = [-1, 0, 1, 2, 3, 4, 5];

export type Step =
  | "address"
  | "type"
  | "category"
  | "size"
  | "floor"
  | "condition"
  | "works"
  | "intention"
  | "contacts";

/** Answers of "Quanto vale la tua casa?": one question per screen. */
export interface ValuationForm {
  place: Place | null;
  /** Position after the owner moved the pin; starts at the found address. */
  latitude: number | null;
  longitude: number | null;
  homeType: HomeType | null;
  category: CadastralCategory | null;
  surface: string;
  rooms: string;
  floor: number | null;
  hasElevator: boolean | null;
  condition: LeadPropertyCondition | null;
  works: BuildingWorks | null;
  intention: OwnerIntention | null;
  fullName: string;
  phone: string;
  privacyAccepted: boolean;
  marketingAccepted: boolean;
}

export const EMPTY_VALUATION: ValuationForm = {
  place: null,
  latitude: null,
  longitude: null,
  homeType: null,
  category: null,
  surface: "",
  rooms: "",
  floor: null,
  hasElevator: null,
  condition: null,
  works: null,
  intention: null,
  fullName: "",
  phone: "",
  privacyAccepted: false,
  marketingAccepted: false,
};

export function isFlat(homeType: HomeType | null): boolean {
  return homeType === "apartment" || homeType === "attic";
}

/** The floor question is only for apartments and attics. */
export function stepsFor(form: ValuationForm): Step[] {
  const steps: Step[] = ["address", "type", "category", "size"];
  if (isFlat(form.homeType)) steps.push("floor");
  steps.push("condition", "works", "intention", "contacts");
  return steps;
}

function wholeNumber(text: string): number | null {
  const value = Number(text.trim().replace(",", "."));
  return Number.isInteger(value) ? value : null;
}

export type StepErrors = Partial<
  Record<"surface" | "rooms" | "fullName" | "phone" | "privacy", string>
>;

/** Same limits as the lead service, so the owner gets feedback before sending. */
export function stepErrors(step: Step, form: ValuationForm): StepErrors {
  const errors: StepErrors = {};
  if (step === "size") {
    const surface = wholeNumber(form.surface);
    if (surface === null || surface < 10 || surface > 5000)
      errors.surface = t("estimate.invalidSurface");
    const rooms = wholeNumber(form.rooms);
    if (rooms === null || rooms < 1 || rooms > 30) errors.rooms = t("estimate.invalidRooms");
  }
  if (step === "contacts") {
    if (form.fullName.trim().length < 2) errors.fullName = t("common.required");
    const digits = form.phone.replace(/[\s\-./()]/g, "").replace(/^00/, "+");
    if (!/^\+?\d{6,15}$/.test(digits)) errors.phone = t("sell.invalidPhone");
    if (!form.privacyAccepted) errors.privacy = t("sell.privacyRequired");
  }
  return errors;
}

/** Whether "Avanti" can be pressed: the question has an answer. */
export function isAnswered(step: Step, form: ValuationForm): boolean {
  switch (step) {
    case "address":
      return form.place !== null && form.latitude !== null && form.longitude !== null;
    case "type":
      return form.homeType !== null;
    case "category":
      return form.category !== null;
    case "size":
      return form.surface.trim() !== "" && form.rooms.trim() !== "";
    case "floor":
      return form.floor !== null && form.hasElevator !== null;
    case "condition":
      return form.condition !== null;
    case "works":
      return form.works !== null;
    case "intention":
      return form.intention !== null;
    case "contacts":
      return true;
  }
}

/** Municipality of the address; the label ends with it when the search did not say. */
function municipalityOf(place: Place): string {
  const fromLabel = place.label.split(",").pop()?.trim() ?? "";
  return (place.municipality ?? fromLabel).slice(0, 80) || "Chieti";
}

export function toValuationRequest(form: ValuationForm): ValuationCreate {
  if (!form.place || form.latitude === null || form.longitude === null) {
    throw new Error("address missing");
  }
  const flat = isFlat(form.homeType);
  return {
    full_name: form.fullName.trim(),
    phone: form.phone.trim(),
    municipality: municipalityOf(form.place),
    property_type: form.homeType ?? "apartment",
    surface_sqm: wholeNumber(form.surface) ?? 0,
    rooms: wholeNumber(form.rooms) ?? 0,
    condition: form.condition ?? "good",
    intention: form.intention ?? "know_value",
    address: form.place.label.slice(0, 200),
    latitude: form.latitude,
    longitude: form.longitude,
    cadastral_category: form.category ?? "unknown",
    building_works: form.works ?? "unknown",
    floor: flat ? form.floor : null,
    has_elevator: flat ? form.hasElevator : null,
    consent: {
      privacy_accepted: true,
      privacy_policy_version: privacy.version,
      marketing_accepted: form.marketingAccepted,
    },
  };
}
