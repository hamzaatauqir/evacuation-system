/**
 * Homepage advertisement logic for the React site.
 *
 * Behaviour is a deliberate port of static/js/site-ads.js (which drives the
 * Flask homepage and the admin preview) so both surfaces treat dismissal,
 * display frequency and click-through URLs identically. Keep the two in sync:
 * the dismissal key format is a storage contract shared with already-deployed
 * browsers, so changing it silently re-shows ads people have dismissed.
 *
 * Pure functions only — storage and fetch are injected by the caller so this
 * stays testable without a DOM (see scripts/homepageAdsSmoke.ts).
 */

export const PUBLIC_ADS_ENDPOINT = "/api/public/advertisements/active";

/** Advertisements are non-essential: abandon a slow fetch, never block the page. */
export const AD_FETCH_TIMEOUT_MS = 8000;

export type DisplayFrequency = "once_per_version" | "once_per_session" | "every_visit";

export interface AdPopup {
  id: number;
  v: number;
  disclosure: string;
  lang: string;
  image: string;
  mobileImage: string;
  alt: string;
  heading: string;
  headingUr: string;
  description: string;
  descriptionUr: string;
  ctaLabel: string;
  ctaUrl: string;
  ctaNewTab: boolean;
  contact: string;
  website: string;
  frequency: DisplayFrequency;
  dismissalHours: number;
}

export interface AdBanner {
  id: number;
  v: number;
  disclosure: string;
  lang: string;
  image: string;
  mobileImage: string;
  alt: string;
  heading: string;
  headingUr: string;
  description: string;
  descriptionUr: string;
  buttonLabel: string;
  buttonUrl: string;
  dismissible: boolean;
}

export interface AdPayload {
  /** Only ever set by the admin preview surface; the public API never sends it. */
  preview?: boolean;
  popup: AdPopup | null;
  banner: AdBanner | null;
}

export interface PublicAdsResponse {
  success?: boolean;
  advertisement?: AdPayload | null;
}

export function popupDismissalKey(id: number | string, version: number | string) {
  return `cwa_ad_dismissed:${id}:${version}`;
}

export function bannerDismissalKey(id: number | string, version: number | string) {
  return `cwa_ad_banner_dismissed:${id}:${version}`;
}

export interface ShouldShowPopupOpts {
  localValue?: string | null;
  sessionValue?: string | null;
  now?: number;
}

/**
 * Whether the popup should be shown. Storage reads are injected to keep this
 * pure. Mirrors shouldShowPopup() in static/js/site-ads.js exactly.
 */
export function shouldShowPopup(popup: AdPopup | null | undefined, opts: ShouldShowPopupOpts = {}) {
  if (!popup) return false;
  const frequency = popup.frequency || "once_per_version";
  if (frequency === "every_visit") return true;
  if (frequency === "once_per_session") return !opts.sessionValue;
  // once_per_version (default)
  if (!opts.localValue) return true;
  const dismissedAt = parseInt(String(opts.localValue), 10);
  if (isNaN(dismissedAt)) return true;
  const hours = parseInt(String(popup.dismissalHours), 10);
  if (isNaN(hours) || hours <= 0) return false; // 0 = never re-show this version
  const now = typeof opts.now === "number" ? opts.now : Date.now();
  return now - dismissedAt >= hours * 3600000;
}

export interface CtaAttributes {
  href: string;
  target: string;
  rel: string;
  external: boolean;
}

/**
 * Validate an admin-entered click-through URL and derive safe link attributes.
 * Returns null when the URL must not be rendered.
 *
 * Defence in depth — the server already rejects unsafe schemes. Only https://
 * and internal '/' paths are allowed; javascript:, data:, http: and
 * protocol-relative URLs are refused.
 */
export function ctaAttributes(
  url: string | null | undefined,
  newTab: boolean | undefined,
  currentHost: string
): CtaAttributes | null {
  const s = String(url || "").trim();
  if (!s) return null;
  let external = false;
  if (s.indexOf("//") === 0) return null; // protocol-relative
  if (s.charAt(0) === "/") {
    external = false;
  } else if (/^https:\/\//i.test(s)) {
    const hostMatch = s.match(/^https:\/\/([^/?#]+)/i);
    if (!hostMatch) return null;
    const host = hostMatch[1].toLowerCase();
    if (host.indexOf("@") !== -1) return null; // embedded credentials
    external = !currentHost || host.split(":")[0] !== String(currentHost).toLowerCase().split(":")[0];
  } else {
    return null; // javascript:, data:, http:, malformed — never render
  }
  const target = newTab ? "_blank" : "";
  return {
    href: s,
    target,
    rel: target === "_blank" ? "noopener noreferrer" : "",
    external,
  };
}

/** Digits-only tel: href, or "" when the number is too short to be callable. */
export function telHref(contact: string | null | undefined) {
  const digits = String(contact || "").replace(/[^0-9+]/g, "");
  return digits.length >= 5 ? `tel:${digits}` : "";
}

/**
 * Whether the popup's body text should start collapsed behind a
 * "Show full details" disclosure.
 *
 * Posters usually already contain the full bilingual announcement, so
 * repeating a long description underneath makes the dialog tall enough to
 * bury the call to action. Nothing is ever dropped — the text is only
 * collapsed, and only when there is enough of it to be worth collapsing, so
 * short advertisements render exactly as before.
 */
export const LONG_TEXT_THRESHOLD = 320;

export function shouldCollapseDetails(popup: AdPopup | null | undefined) {
  if (!popup) return false;
  if (!popup.image) return false; // no poster => the text is the whole ad
  const combined = `${popup.description || ""}${popup.descriptionUr || ""}`;
  return combined.length > LONG_TEXT_THRESHOLD;
}
