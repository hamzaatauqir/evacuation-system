/**
 * Single source of truth for resolving the backend origin.
 *
 * The frontend (cwakuwait.com) and the backend (the Python portal) are separate
 * Render services on different origins, so every API call needs an absolute
 * backend origin. Three call sites used to resolve it independently and
 * disagreed; they now all go through here.
 *
 * Two failure modes this guards against:
 *
 * 1. Unreplaced build placeholders. index.html uses Vite's `%VITE_X%` HTML env
 *    substitution. When a variable is undefined at build time the literal
 *    `%VITE_X%` survives into the output and must be treated as "not
 *    configured" rather than used as a URL. See isUnreplacedPlaceholder.
 *
 * 2. portal.cwakuwait.com. This host is retired and currently answers 403, so a
 *    configured value pointing at it is deliberately ignored rather than
 *    honoured.
 */

/**
 * A Vite HTML placeholder that was never substituted, e.g. "%VITE_API_BASE_URL%".
 *
 * Deliberately matched structurally (leading + trailing '%') instead of by
 * comparing against the placeholder's own text. The original index.html
 * compared the substituted value against a sentinel written as that same
 * placeholder token, so the build rewrote *both* sides to the same string, the
 * comparison always matched, and every configured backend URL was discarded.
 */
const UNREPLACED_PLACEHOLDER_RE = /^%.+%$/;

/** Retired backend host — answers 403; never use it even if configured. */
const DEPRECATED_PORTAL_HOST_RE = /^https?:\/\/portal\.cwakuwait\.com(?:\/|$)/i;

const LOCAL_HOST_RE = /^(localhost|127\.0\.0\.1)$/i;

const LOCALHOST_URL_RE = /^https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?$/i;

/**
 * Last-resort default when no VITE_* origin is configured.
 *
 * Set VITE_API_BASE_URL on the frontend service instead of relying on this —
 * it exists only so a missing variable degrades to a working backend rather
 * than to the retired portal host (the previous default) or to the frontend's
 * own origin (which would make the alias routes redirect to themselves).
 */
export const DEFAULT_PUBLIC_BACKEND_ORIGIN = "https://evacuation-system.onrender.com";

/** Frontend hosts that are served by a different origin than the backend. */
export const CUSTOM_DOMAIN_HOSTS = new Set([
  "cwakuwait.com",
  "www.cwakuwait.com",
  "community-welfare-ui.onrender.com",
]);

export interface ViteEnvLike {
  VITE_API_BASE_URL?: string;
  VITE_BACKEND_PORTAL_URL?: string;
  PROD?: boolean;
}

/**
 * import.meta.env, or {} outside a Vite build.
 *
 * Vite statically replaces `import.meta.env` at build time; under plain Node
 * (the smoke tests) it is undefined, so the `?? {}` keeps property reads from
 * throwing and lets the resolvers be exercised with injected env objects.
 */
export function viteEnv(): ViteEnvLike {
  try {
    return (import.meta.env as ViteEnvLike | undefined) ?? {};
  } catch (_err) {
    return {};
  }
}

export function trimTrailingSlash(value: string) {
  return value.trim().replace(/\/+$/, "");
}

export function isUnreplacedPlaceholder(value: string) {
  return UNREPLACED_PLACEHOLDER_RE.test(value.trim());
}

export function isDeprecatedPortalOrigin(value: string) {
  return DEPRECATED_PORTAL_HOST_RE.test(value.trim());
}

export function isLocalhostUrl(value: string) {
  return LOCALHOST_URL_RE.test(value.trim());
}

export function isLocalHostname(hostname: string) {
  return LOCAL_HOST_RE.test(hostname || "");
}

/**
 * Normalise one configured value, or return "" when it must not be used.
 * "" means "not configured" so callers can fall through to their own defaults.
 */
export function sanitizeConfiguredOrigin(value?: string) {
  const trimmed = trimTrailingSlash(value || "");
  if (!trimmed) return "";
  if (isUnreplacedPlaceholder(trimmed)) return "";
  if (isDeprecatedPortalOrigin(trimmed)) return "";
  return trimmed;
}

/** First usable value, in priority order. "" when none are usable. */
export function firstConfiguredOrigin(...values: Array<string | undefined>) {
  for (const value of values) {
    const sanitized = sanitizeConfiguredOrigin(value);
    if (sanitized) return sanitized;
  }
  return "";
}

/** Backend origin to use when running against a local dev server. */
export function localBackendOrigin(location?: { protocol?: string; hostname?: string; port?: string }) {
  const protocol = location?.protocol || "http:";
  const hostname = location?.hostname || "localhost";
  const port = location?.port || "";
  if (isLocalHostname(hostname)) {
    const targetPort = port && port !== "8080" ? "8080" : port || "8080";
    return `${protocol}//${hostname}:${targetPort}`;
  }
  return "http://localhost:8080";
}

export function joinBaseAndPath(base: string, path: string) {
  if (/^https?:\/\//i.test(path.trim())) return trimTrailingSlash(path);
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const trimmedBase = trimTrailingSlash(base);
  if (!trimmedBase) return normalized;
  return `${trimmedBase}${normalized}`;
}

// ── Resolvers ──────────────────────────────────────────────────────
// These live here, alongside the sanitisers and free of relative imports, so
// scripts/apiBaseSmoke.ts can exercise them under plain Node.

export interface LocationLike {
  protocol?: string;
  hostname?: string;
  port?: string;
  origin?: string;
  pathname?: string;
}

function currentLocation(location?: LocationLike): LocationLike | undefined {
  return location ?? (typeof window !== "undefined" ? window.location : undefined);
}

/**
 * Base URL for API calls. Configured VITE_* values win; "" means same-origin
 * relative paths (correct only when the backend serves the page).
 */
export function resolveApiBaseUrl(
  primary?: string,
  fallback?: string,
  env: ViteEnvLike = viteEnv(),
  location?: LocationLike
) {
  const candidate = firstConfiguredOrigin(primary, fallback);
  // A localhost base baked into a production build is a misconfiguration.
  if (candidate && !(env.PROD && isLocalhostUrl(candidate))) return candidate;

  const loc = currentLocation(location);
  if (isLocalHostname(loc?.hostname || "")) return localBackendOrigin(loc);
  if (env.PROD) return "";
  return loc?.origin ? trimTrailingSlash(loc.origin) : localBackendOrigin(loc);
}

/**
 * Backend origin serving the real public forms (/embassy-registration etc).
 *
 * Configured VITE_* values win. This previously fell back to
 * portal.cwakuwait.com, which is retired and answers 403 — that default is why
 * the /register, /apply and /transit aliases broke on cwakuwait.com.
 */
export function resolvePublicBackendPortal(env: ViteEnvLike = viteEnv(), location?: LocationLike) {
  const configured = firstConfiguredOrigin(env.VITE_BACKEND_PORTAL_URL, env.VITE_API_BASE_URL);
  if (configured) return configured;

  const loc = currentLocation(location);
  if (!loc) return DEFAULT_PUBLIC_BACKEND_ORIGIN;

  const hostname = (loc.hostname || "").toLowerCase();
  if (isLocalHostname(hostname)) return localBackendOrigin(loc);
  if (CUSTOM_DOMAIN_HOSTS.has(hostname)) return DEFAULT_PUBLIC_BACKEND_ORIGIN;
  return loc.origin ? trimTrailingSlash(loc.origin) : DEFAULT_PUBLIC_BACKEND_ORIGIN;
}

/**
 * True when navigating to `target` would just reload the current page.
 *
 * The alias routes (/register, /apply, …) forward to the backend's real form.
 * If the resolved backend origin is the frontend's own origin, that forward
 * lands back on this SPA, which forwards again — an infinite reload. Callers
 * skip the navigation and leave the manual link visible instead.
 */
export function isSelfReferentialTarget(target: string, location?: LocationLike) {
  const loc = currentLocation(location);
  if (!loc?.origin) return false;
  try {
    const resolved = new URL(target, loc.origin);
    const currentPath = trimTrailingSlash(loc.pathname || "/") || "/";
    const targetPath = trimTrailingSlash(resolved.pathname || "/") || "/";
    return resolved.origin === loc.origin && targetPath === currentPath;
  } catch (_err) {
    return false;
  }
}
