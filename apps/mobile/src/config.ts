/** App configuration. Values marked TODO must be replaced with the agency's real data. */

export const config = {
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:5173",
  // Web version on Netlify: wake the services on Render's free plan as soon as the app
  // opens (they sleep when idle). Only with apiBaseUrl "", i.e. the API on the same site.
  warmUpServices: process.env.EXPO_PUBLIC_WARM_UP_SERVICES === "true",
};

/**
 * Features that can be switched off without removing their code.
 * threeD: the "Vedi in 3D" button, the 3D badge on photos and the 3D viewer
 * (hidden for now; set to true to show them again).
 */
export const features = {
  threeD: false,
};

export const agency = {
  name: "Immobiliare Taraborrelli",
  area: "Chieti e Chieti Scalo",
  // Office landline: used by every "Chiama" button.
  phone: "+390871271706",
  phoneLabel: "0871 271706",
  // Mobile: second call option in Contattaci, and the WhatsApp number.
  mobile: "+393405383065",
  mobileLabel: "340 538 3065",
  whatsapp: "393405383065",
  email: "immobiliaretaraborrelli@gmail.com",
  address: "Chieti",
};

/** Privacy notice accepted in the forms. TODO: URL of the agency's published notice. */
export const privacy = {
  version: "2026-01",
  url: "",
};
