// Creates sample properties through the real admin API, for the local trial environment.
// Usage: node scripts/demo/seed.mjs <api-base-url> <admin-email> <admin-password>
// The listings are fictional and their photos are labelled "Foto di esempio".
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const [base = "http://localhost:5173", email, password] = process.argv.slice(2);
const here = dirname(fileURLToPath(import.meta.url));

const PROPERTIES = [
  {
    contract: "sale",
    property_type: "apartment",
    title: "Trilocale luminoso con balcone",
    description:
      "Appartamento di esempio al secondo piano con ascensore, soggiorno, cucina abitabile, due camere e balcone con vista.",
    price: 139000,
    condominium_fees: 70,
    surface_sqm: 95,
    rooms: 3,
    bedrooms: 2,
    bathrooms: 1,
    floor: 2,
    total_floors: 4,
    condition: "good",
    energy_class: "C",
    features: ["balcony", "elevator", "cellar"],
    is_featured: true,
    municipality: "Chieti",
    zone: "Centro",
    latitude: "42.351",
    longitude: "14.168",
  },
  {
    contract: "sale",
    property_type: "villa",
    title: "Villa indipendente con giardino",
    description:
      "Villa di esempio su due livelli con ampio giardino, box auto e taverna. Zona tranquilla e servita.",
    price: 345000,
    surface_sqm: 240,
    rooms: 6,
    bedrooms: 4,
    bathrooms: 3,
    condition: "renovated",
    energy_class: "B",
    features: ["garden", "garage", "terrace", "autonomous_heating"],
    is_featured: true,
    municipality: "Chieti",
    zone: "Colle dell'Ara",
    latitude: "42.366",
    longitude: "14.150",
  },
  {
    contract: "rent",
    property_type: "apartment",
    title: "Bilocale arredato vicino all'università",
    description:
      "Bilocale di esempio arredato, a pochi minuti a piedi dal campus. Ideale per studenti o giovani lavoratori.",
    price: 450,
    surface_sqm: 50,
    rooms: 2,
    bedrooms: 1,
    bathrooms: 1,
    floor: 1,
    condition: "good",
    energy_class: "D",
    features: ["furnished", "air_conditioning"],
    is_featured: true,
    municipality: "Chieti Scalo",
    tenant_types: ["students", "workers"],
    accommodation: "entire_property",
    available_from: "2026-11-01",
  },
  {
    contract: "rent",
    property_type: "apartment",
    title: "Stanza singola in appartamento condiviso",
    description:
      "Stanza singola di esempio in appartamento con altri due studenti, cucina e bagno in comune.",
    price: 280,
    surface_sqm: 90,
    rooms: 4,
    bedrooms: 3,
    bathrooms: 2,
    features: ["furnished"],
    municipality: "Chieti Scalo",
    tenant_types: ["students"],
    accommodation: "single_room",
    available_from: "2026-10-20",
  },
  {
    contract: "sale",
    property_type: "attic",
    title: "Attico con terrazzo panoramico",
    description: "Attico di esempio all'ultimo piano con terrazzo abitabile e vista sulla Maiella.",
    price: 210000,
    surface_sqm: 110,
    rooms: 4,
    bedrooms: 2,
    bathrooms: 2,
    floor: 5,
    total_floors: 5,
    condition: "new",
    energy_class: "A2",
    features: ["terrace", "elevator", "parking", "air_conditioning"],
    municipality: "Chieti",
    zone: "Tricalle",
    latitude: "42.355",
    longitude: "14.176",
  },
];

async function call(path, { token, json, form, method = "POST" } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (json) headers["Content-Type"] = "application/json";
  const response = await fetch(`${base}${path}`, {
    method,
    headers,
    body: json ? JSON.stringify(json) : form,
  });
  if (!response.ok)
    throw new Error(`${method} ${path} → ${response.status} ${await response.text()}`);
  return response.status === 204 ? undefined : response.json();
}

const { access_token: token } = await call("/api/v1/auth/login", { json: { email, password } });

for (const [index, property] of PROPERTIES.entries()) {
  const created = await call("/api/v1/property/admin/properties", { token, json: property });
  const photo = await readFile(join(here, `esempio-${index + 1}.jpg`));
  const form = new FormData();
  form.append("file", new Blob([photo], { type: "image/jpeg" }), `esempio-${index + 1}.jpg`);
  form.append("caption", "Foto di esempio");
  await call(`/api/v1/property/admin/properties/${created.id}/photos`, { token, form });
  await call(`/api/v1/property/admin/properties/${created.id}/status`, {
    token,
    json: { status: "published" },
  });
}

console.log(`${PROPERTIES.length} immobili di esempio pubblicati`);
