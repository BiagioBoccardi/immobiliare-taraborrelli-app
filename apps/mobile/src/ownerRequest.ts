import type { OwnerIntention, OwnerRequestCreate } from "@taraborrelli/api-client";

import { privacy } from "./config";
import { t } from "./i18n";

/** Property types accepted by the lead service (the catalog has a few more). */
export type OwnerPropertyType = OwnerRequestCreate["property_type"];

/** Short "Voglio vendere / affittare" form: only what is needed to call the owner back. */
export interface OwnerForm {
  kind: "sell" | "rent";
  fullName: string;
  phone: string;
  municipality: string;
  propertyType: OwnerPropertyType;
  intention: OwnerIntention | null;
  message: string;
  privacyAccepted: boolean;
  marketingAccepted: boolean;
}

export const EMPTY_OWNER_FORM: OwnerForm = {
  kind: "sell",
  fullName: "",
  phone: "",
  municipality: "Chieti",
  propertyType: "apartment",
  intention: null,
  message: "",
  privacyAccepted: false,
  marketingAccepted: false,
};

export type OwnerFormErrors = Partial<Record<keyof OwnerForm, string>>;

/** Same rules as the lead service, checked before sending to give immediate feedback. */
export function validateOwnerForm(form: OwnerForm): OwnerFormErrors {
  const errors: OwnerFormErrors = {};
  if (form.fullName.trim().length < 2) errors.fullName = t("common.required");
  const digits = form.phone.replace(/[\s\-./()]/g, "").replace(/^00/, "+");
  if (!/^\+?\d{6,15}$/.test(digits)) errors.phone = t("sell.invalidPhone");
  if (form.municipality.trim().length < 2) errors.municipality = t("common.required");
  if (!form.intention) errors.intention = t("common.required");
  if (!form.privacyAccepted) errors.privacyAccepted = t("sell.privacyRequired");
  return errors;
}

export function toOwnerRequest(form: OwnerForm): OwnerRequestCreate {
  return {
    kind: form.kind,
    full_name: form.fullName.trim(),
    phone: form.phone.trim(),
    municipality: form.municipality.trim(),
    property_type: form.propertyType,
    intention: form.intention ?? "know_value",
    message: form.message.trim() || null,
    consent: {
      privacy_accepted: true,
      privacy_policy_version: privacy.version,
      marketing_accepted: form.marketingAccepted,
    },
  };
}
