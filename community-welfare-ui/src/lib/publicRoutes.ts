const LOCAL_HOST_RE = /^(localhost|127\.0\.0\.1)$/i;
const CUSTOM_DOMAIN_HOSTS = new Set([
  "cwakuwait.com",
  "www.cwakuwait.com",
  "community-welfare-ui.onrender.com",
]);

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function firstConfiguredValue(...values: Array<string | undefined>) {
  for (const value of values) {
    const trimmed = (value || "").trim();
    if (trimmed) return trimmed;
  }
  return "";
}

function resolvePublicBackendPortal() {
  const configured = firstConfiguredValue(
    import.meta.env.VITE_BACKEND_PORTAL_URL,
    import.meta.env.VITE_API_BASE_URL
  );
  if (configured) return trimTrailingSlash(configured);
  if (typeof window === "undefined") return "https://portal.cwakuwait.com";

  const { protocol, hostname, origin, port } = window.location;
  if (LOCAL_HOST_RE.test(hostname)) {
    const targetPort = port && port !== "8080" ? "8080" : port || "8080";
    return `${protocol}//${hostname}:${targetPort}`;
  }
  if (CUSTOM_DOMAIN_HOSTS.has(hostname.toLowerCase())) {
    return "https://portal.cwakuwait.com";
  }
  return trimTrailingSlash(origin);
}

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
