/**
 * Shared country code mapping utility
 * Maps various country name variations to ISO 3166-1 alpha-2 country codes
 */

const COUNTRY_MAP: Record<string, string> = {
  // United States
  'united states': 'US',
  'united states of america': 'US',
  usa: 'US',
  us: 'US',
  american: 'US',

  // Vietnam
  vietnam: 'VN',
  vietnamese: 'VN',
  'viet nam': 'VN',
  vn: 'VN',

  // China
  china: 'CN',
  chinese: 'CN',
  cn: 'CN',

  // India
  india: 'IN',
  indian: 'IN',
  in: 'IN',

  // Mexico
  mexico: 'MX',
  mexican: 'MX',
  mx: 'MX',

  // Russia
  russia: 'RU',
  russian: 'RU',
  ru: 'RU',
  'russian federation': 'RU',
};

/**
 * Resolves a country name to its ISO 3166-1 alpha-2 country code
 * @param value - The country name or code to resolve
 * @returns The ISO country code or null if not found
 */
export function resolveCountryCode(
  value: string | null | undefined,
): string | null {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) {
    return null;
  }

  return COUNTRY_MAP[normalized] || null;
}
