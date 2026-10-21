import type { Feature, TenantType } from "@taraborrelli/api-client";
import { useState, type FormEvent } from "react";

import { t, tEnum } from "../i18n";
import {
  ACCOMMODATIONS,
  CONDITIONS,
  CONTRACTS,
  ENERGY_CLASSES,
  FEATURES,
  PROPERTY_TYPES,
  TENANT_TYPES,
  validateForm,
  type FormErrors,
  type PropertyFormState,
} from "../pages/propertyForm";
import { Field } from "./ui";

type TextKey = {
  [K in keyof PropertyFormState]: PropertyFormState[K] extends string ? K : never;
}[keyof PropertyFormState];

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

export function PropertyForm({
  initial,
  submitting,
  onSubmit,
}: {
  initial: PropertyFormState;
  submitting: boolean;
  onSubmit: (form: PropertyFormState) => void;
}) {
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState<FormErrors>({});

  const set = <K extends keyof PropertyFormState>(name: K, value: PropertyFormState[K]) =>
    setForm((current) => ({ ...current, [name]: value }));

  const input = (name: TextKey, type: "text" | "number" | "date" = "text", extra = {}) => (
    <input
      id={name}
      name={name}
      type={type}
      value={form[name]}
      aria-invalid={Boolean(errors[name])}
      onChange={(e) => set(name, e.target.value as PropertyFormState[typeof name])}
      {...extra}
    />
  );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = validateForm(form);
    setErrors(found);
    if (Object.keys(found).length === 0) onSubmit(form);
  };

  const isRent = form.contract === "rent";

  return (
    <form className="stack" onSubmit={submit} noValidate>
      <section className="card stack">
        <h2>{t("properties.sectionListing")}</h2>
        <div className="grid-2">
          <Field label={t("properties.contract")} htmlFor="contract">
            <select
              id="contract"
              value={form.contract}
              onChange={(e) => set("contract", e.target.value as PropertyFormState["contract"])}
            >
              {CONTRACTS.map((value) => (
                <option key={value} value={value}>
                  {tEnum("contract", value)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("properties.type")} htmlFor="property_type">
            <select
              id="property_type"
              value={form.property_type}
              onChange={(e) =>
                set("property_type", e.target.value as PropertyFormState["property_type"])
              }
            >
              {PROPERTY_TYPES.map((value) => (
                <option key={value} value={value}>
                  {tEnum("propertyType", value)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field
          label={t("properties.externalRef")}
          htmlFor="external_ref"
          hint={t("properties.externalRefHint")}
        >
          {input("external_ref", "text", { maxLength: 50 })}
        </Field>
        <Field label={t("properties.titleField")} htmlFor="title" error={errors.title}>
          {input("title", "text", { maxLength: 120 })}
        </Field>
        <Field label={t("properties.description")} htmlFor="description">
          <textarea
            id="description"
            maxLength={10000}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
          />
        </Field>
        <div className="grid-2">
          <Field
            label={isRent ? t("properties.priceRent") : t("properties.price")}
            htmlFor="price"
            error={errors.price}
          >
            {input("price", "number", { min: 0 })}
          </Field>
          <Field label={t("properties.condominiumFees")} htmlFor="condominium_fees">
            {input("condominium_fees", "number", { min: 0 })}
          </Field>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={form.is_featured}
            onChange={(e) => set("is_featured", e.target.checked)}
          />
          {t("properties.featured")}
        </label>
      </section>

      <section className="card stack">
        <h2>{t("properties.sectionFeatures")}</h2>
        <div className="grid-3">
          <Field label={t("properties.surface")} htmlFor="surface_sqm" error={errors.surface_sqm}>
            {input("surface_sqm", "number", { min: 1 })}
          </Field>
          <Field label={t("properties.rooms")} htmlFor="rooms">
            {input("rooms", "number", { min: 0 })}
          </Field>
          <Field label={t("properties.bedrooms")} htmlFor="bedrooms">
            {input("bedrooms", "number", { min: 0 })}
          </Field>
          <Field label={t("properties.bathrooms")} htmlFor="bathrooms">
            {input("bathrooms", "number", { min: 0 })}
          </Field>
          <Field label={t("properties.floor")} htmlFor="floor">
            {input("floor", "number")}
          </Field>
          <Field label={t("properties.totalFloors")} htmlFor="total_floors">
            {input("total_floors", "number", { min: 0 })}
          </Field>
          <Field label={t("properties.yearBuilt")} htmlFor="year_built">
            {input("year_built", "number")}
          </Field>
          <Field label={t("properties.condition")} htmlFor="condition">
            <select
              id="condition"
              value={form.condition}
              onChange={(e) => set("condition", e.target.value as PropertyFormState["condition"])}
            >
              <option value="">{t("common.none")}</option>
              {CONDITIONS.map((value) => (
                <option key={value} value={value}>
                  {tEnum("condition", value)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("properties.energyClass")} htmlFor="energy_class">
            <select
              id="energy_class"
              value={form.energy_class}
              onChange={(e) =>
                set("energy_class", e.target.value as PropertyFormState["energy_class"])
              }
            >
              <option value="">{t("common.none")}</option>
              {ENERGY_CLASSES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <fieldset className="field">
          <legend className="field-label">{t("properties.features")}</legend>
          <div className="checkbox-group">
            {FEATURES.map((feature: Feature) => (
              <label key={feature} className="checkbox">
                <input
                  type="checkbox"
                  checked={form.features.includes(feature)}
                  onChange={() => set("features", toggle(form.features, feature))}
                />
                {tEnum("feature", feature)}
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      <section className="card stack">
        <h2>{t("properties.sectionLocation")}</h2>
        <div className="grid-2">
          <Field
            label={t("properties.municipality")}
            htmlFor="municipality"
            error={errors.municipality}
          >
            {input("municipality", "text", { maxLength: 80 })}
          </Field>
          <Field label={t("properties.zone")} htmlFor="zone">
            {input("zone", "text", { maxLength: 80 })}
          </Field>
        </div>
        <Field label={t("properties.address")} htmlFor="address">
          {input("address", "text", { maxLength: 200 })}
        </Field>
        <div className="grid-2">
          <Field label={t("properties.latitude")} htmlFor="latitude">
            {input("latitude", "text", { inputMode: "decimal" })}
          </Field>
          <Field label={t("properties.longitude")} htmlFor="longitude" error={errors.longitude}>
            {input("longitude", "text", { inputMode: "decimal" })}
          </Field>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={form.show_exact_location}
            onChange={(e) => set("show_exact_location", e.target.checked)}
          />
          {t("properties.showExactLocation")}
        </label>
        <span className="hint">{t("properties.locationHint")}</span>
      </section>

      {isRent ? (
        <section className="card stack">
          <h2>{t("properties.sectionRental")}</h2>
          <fieldset className="field">
            <legend className="field-label">{t("properties.tenantTypes")}</legend>
            <div className="row">
              {TENANT_TYPES.map((tenant: TenantType) => (
                <label key={tenant} className="checkbox">
                  <input
                    type="checkbox"
                    checked={form.tenant_types.includes(tenant)}
                    onChange={() => set("tenant_types", toggle(form.tenant_types, tenant))}
                  />
                  {tEnum("tenantType", tenant)}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="grid-2">
            <Field label={t("properties.accommodation")} htmlFor="accommodation">
              <select
                id="accommodation"
                value={form.accommodation}
                onChange={(e) =>
                  set("accommodation", e.target.value as PropertyFormState["accommodation"])
                }
              >
                <option value="">{t("common.none")}</option>
                {ACCOMMODATIONS.map((value) => (
                  <option key={value} value={value}>
                    {tEnum("accommodation", value)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("properties.availableFrom")} htmlFor="available_from">
              {input("available_from", "date")}
            </Field>
          </div>
        </section>
      ) : null}

      <div className="row">
        <button type="submit" className="button button-primary" disabled={submitting}>
          {submitting ? t("common.saving") : t("common.save")}
        </button>
      </div>
    </form>
  );
}
