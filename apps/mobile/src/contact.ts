import { Linking } from "react-native";

import { agency } from "./config";
import { whatsappUrl } from "./format";

/** Quick contact with the agency (CLAUDE.md, section 13): phone, WhatsApp, email. */
export const contact = {
  call: (number: string = agency.phone) => Linking.openURL(`tel:${number}`),
  whatsapp: (message: string) => Linking.openURL(whatsappUrl(agency.whatsapp, message)),
  email: (subject: string) =>
    Linking.openURL(`mailto:${agency.email}?subject=${encodeURIComponent(subject)}`),
};
