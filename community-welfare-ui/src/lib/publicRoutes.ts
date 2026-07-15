import {
  isSelfReferentialTarget,
  resolvePublicBackendPortal,
  trimTrailingSlash,
} from "./backendOrigin";

// Backend-origin resolution lives in ./backendOrigin (single source of truth).
export { isSelfReferentialTarget, resolvePublicBackendPortal };

export const PUBLIC_PORTAL = resolvePublicBackendPortal();

export const PUBLIC_PORTAL_PATHS = {
  ksaRegister: "/embassy-registration",
  ksaTrack: "/track-application",
} as const;

export const PUBLIC_KSA_ALIAS_PATHS = [
  "/register",
  "/embassy-registration",
  "/ksa-transit",
  "/transit-visa",
  "/apply",
  "/transit",
] as const;

export function publicPortalUrl(path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${trimTrailingSlash(PUBLIC_PORTAL)}${normalized}`;
}

export function navigateToPublicPortal(path: string, options?: { replace?: boolean }) {
  const target = publicPortalUrl(path);
  if (isSelfReferentialTarget(target)) {
    try {
      console.warn("[CWA] Skipped self-referential portal redirect", target);
    } catch (_err) {}
    return;
  }
  if (typeof document !== "undefined") {
    document.body.style.cursor = "progress";
  }
  if (typeof window !== "undefined") {
    try {
      console.info("[CWA] KSA Transit link clicked", target);
    } catch (_err) {}
    if (options?.replace) {
      window.location.replace(target);
    } else {
      window.location.assign(target);
    }
  }
}
