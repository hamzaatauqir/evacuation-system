import { BACKEND_PORTAL, buildBackendUrl } from "./api";

export const PUBLIC_PORTAL = BACKEND_PORTAL;

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
  return buildBackendUrl(path);
}

export function navigateToPublicPortal(path: string, options?: { replace?: boolean }) {
  const target = publicPortalUrl(path);
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
