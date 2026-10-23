/**
 * Mortgage calculator: fixed rate, French amortization (equal monthly payments).
 * The result is indicative and never a quote (CLAUDE.md, section 11).
 */

export const MORTGAGE_YEARS = [10, 15, 20, 25, 30] as const;
export const DEFAULT_YEARS = 25;
/** Example rate shown at first: the user replaces it with the one offered by the bank. */
export const DEFAULT_RATE = 3;
export const DEFAULT_DOWN_PAYMENT_SHARE = 0.2;
/** Banks usually lend up to this share of the property value. */
export const USUAL_MAX_LOAN_SHARE = 0.8;
export const MAX_RATE = 15;

export interface MortgageInput {
  price: number;
  downPayment: number;
  years: number;
  /** Annual nominal rate, in percent (3 means 3%). */
  annualRate: number;
}

export interface MortgageResult {
  loan: number;
  monthlyPayment: number;
  totalPaid: number;
  totalInterest: number;
  /** Share of the price covered by the loan, from 0 to 1. */
  loanShare: number;
}

export type MortgageError = "invalidPrice" | "invalidDownPayment" | "invalidRate";

/** Reads a number typed the Italian way: "120.000", "120000 €", "3,5". Null if not a number. */
export function parseNumber(text: string): number | null {
  const cleaned = text.replace(/[€\s]/g, "");
  if (!cleaned) return null;
  // Dots are thousands separators unless there is no comma and they look decimal ("3.5").
  const normalized = cleaned.includes(",")
    ? cleaned.replace(/\./g, "").replace(",", ".")
    : /^\d{1,3}(\.\d{3})+$/.test(cleaned)
      ? cleaned.replace(/\./g, "")
      : cleaned;
  if (!/^\d+(\.\d+)?$/.test(normalized)) return null;
  return Number(normalized);
}

/** Monthly payment of a loan: P·r / (1 − (1 + r)^−n), or P / n with a zero rate. */
export function monthlyPayment(loan: number, annualRate: number, years: number): number {
  const months = years * 12;
  const rate = annualRate / 100 / 12;
  if (rate === 0) return loan / months;
  return (loan * rate) / (1 - Math.pow(1 + rate, -months));
}

export function validateMortgage(input: MortgageInput): MortgageError | null {
  if (!Number.isFinite(input.price) || input.price <= 0) return "invalidPrice";
  if (input.downPayment < 0 || input.downPayment >= input.price) return "invalidDownPayment";
  if (input.annualRate < 0 || input.annualRate > MAX_RATE) return "invalidRate";
  return null;
}

export function computeMortgage(input: MortgageInput): MortgageResult {
  const loan = input.price - input.downPayment;
  const payment = monthlyPayment(loan, input.annualRate, input.years);
  const totalPaid = payment * input.years * 12;
  return {
    loan,
    monthlyPayment: payment,
    totalPaid,
    totalInterest: totalPaid - loan,
    loanShare: loan / input.price,
  };
}

export function defaultDownPayment(price: number): number {
  return Math.round((price * DEFAULT_DOWN_PAYMENT_SHARE) / 1000) * 1000;
}
