export function isValidEmail(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized);
}

export function isValidPhoneNumber(value: string): boolean {
  const normalized = value
    .replace(/[\s().-]/g, "")
    .replace(/^\+/, "")
    .trim();
  return /^[0-9]{7,15}$/.test(normalized);
}

export const EMAIL_DOMAIN_SUGGESTIONS: readonly string[] = [
  "gmail.com",
  "googlemail.com",
  "outlook.com",
  "hotmail.com",
  "live.com",
  "icloud.com",
  "yahoo.com",
  "proton.me",
  "protonmail.com",
  "zoho.com",
  "gmx.com",
  "fastmail.com",
];

export function suggestEmailDomains(value: string, limit = 4): string[] {
  const at = value.indexOf("@");
  if (at <= 0) return [];

  const local = value.slice(0, at);
  const domain = value
    .slice(at + 1)
    .trim()
    .toLowerCase();

  // An address that already looks complete offers nothing to correct, and a blank
  // domain would otherwise produce a list of every suggestion at once.
  if (!domain || isValidEmail(value)) return [];
  if (at !== value.lastIndexOf("@")) return [];

  return EMAIL_DOMAIN_SUGGESTIONS.filter((candidate) => candidate.startsWith(domain))
    .slice(0, limit)
    .map((candidate) => `${local}@${candidate}`);
}

export function phoneValidationMessage(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  return isValidPhoneNumber(trimmed) ? undefined : "Enter a valid phone number.";
}

export function passwordChecks(value: string) {
  const checks = {
    length: value.length >= 10,
    letter: /[A-Za-z]/.test(value),
    number: /\d/.test(value),
    symbol: /[^A-Za-z0-9]/.test(value),
  };

  return {
    score: Object.values(checks).filter(Boolean).length,
    valid: checks.length && checks.letter && checks.number,
    checks,
  };
}
