import type { RegisterIn } from "@taraborrelli/api-client";

import { privacy } from "./config";
import { t } from "./i18n";

export interface RegisterForm {
  fullName: string;
  email: string;
  password: string;
  privacyAccepted: boolean;
  marketingAccepted: boolean;
}

export const EMPTY_REGISTER_FORM: RegisterForm = {
  fullName: "",
  email: "",
  password: "",
  privacyAccepted: false,
  marketingAccepted: false,
};

export type RegisterErrors = Partial<Record<keyof RegisterForm, string>>;

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Same rules as the auth service (password of at least 10 characters). */
export function validateRegister(form: RegisterForm): RegisterErrors {
  const errors: RegisterErrors = {};
  if (form.fullName.trim().length < 2) errors.fullName = t("common.required");
  if (!EMAIL.test(form.email.trim())) errors.email = t("auth.invalidEmail");
  if (form.password.length < 10) errors.password = t("auth.shortPassword");
  if (!form.privacyAccepted) errors.privacyAccepted = t("auth.privacyRequired");
  return errors;
}

export function toRegisterIn(form: RegisterForm): RegisterIn {
  return {
    full_name: form.fullName.trim(),
    email: form.email.trim(),
    password: form.password,
    source: "app",
    consent: {
      privacy_accepted: true,
      privacy_policy_version: privacy.version,
      marketing_accepted: form.marketingAccepted,
    },
  };
}
