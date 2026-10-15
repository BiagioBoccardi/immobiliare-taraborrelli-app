/** App configuration. Values marked TODO must be replaced with the agency's real data. */

export const config = {
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:5173",
};

export const agency = {
  name: "Immobiliare Taraborrelli",
  area: "Chieti e Chieti Scalo",
  // TODO: real contact details of the agency.
  phone: "+390000000000",
  phoneLabel: "+39 000 000 0000",
  whatsapp: "390000000000",
  email: "info@immobiliaretaraborrelli.it",
  address: "Chieti",
};

/** Privacy notice accepted in the forms. TODO: URL of the agency's published notice. */
export const privacy = {
  version: "2026-01",
  url: "",
};
