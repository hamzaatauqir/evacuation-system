const LOCAL_HOST_RE = /^(localhost|127\.0\.0\.1)$/i;
const DEPRECATED_PORTAL_HOST_RE = /^https?:\/\/portal\.cwakuwait\.com(?:\/|$)/i;

function trimTrailingSlash(value: string) {
  return value.trim().replace(/\/+$/, "");
}

function isAbsoluteUrl(value: string) {
  return /^https?:\/\//i.test(value.trim());
}

function isLocalhostUrl(value: string) {
  return /^https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?$/i.test(value.trim());
}

function sanitizeConfiguredBase(value?: string) {
  const trimmed = trimTrailingSlash(value || "");
  if (!trimmed || DEPRECATED_PORTAL_HOST_RE.test(trimmed)) return "";
  return trimmed;
}

function localBackendOrigin() {
  if (typeof window !== "undefined" && window.location) {
    const { protocol, hostname, port } = window.location;
    if (LOCAL_HOST_RE.test(hostname)) {
      const targetPort = port && port !== "8080" ? "8080" : port || "8080";
      return `${protocol}//${hostname}:${targetPort}`;
    }
  }
  return "http://localhost:8080";
}

function browserOrigin() {
  if (typeof window !== "undefined" && window.location?.origin) {
    return trimTrailingSlash(window.location.origin);
  }
  return localBackendOrigin();
}

function resolveBaseUrl(primary?: string, fallback?: string) {
  const candidate = sanitizeConfiguredBase(primary) || sanitizeConfiguredBase(fallback);
  if (candidate && !(import.meta.env.PROD && isLocalhostUrl(candidate))) {
    return candidate;
  }
  if (typeof window !== "undefined" && LOCAL_HOST_RE.test(window.location?.hostname || "")) {
    return localBackendOrigin();
  }
  return import.meta.env.PROD ? "" : browserOrigin();
}

function joinBaseAndPath(base: string, path: string) {
  if (isAbsoluteUrl(path)) return trimTrailingSlash(path);
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const trimmedBase = trimTrailingSlash(base);
  if (!trimmedBase) return normalized;
  return `${trimmedBase}${normalized}`;
}

function displayBaseUrl(base: string) {
  if (base) return base;
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "this site";
}

const API_BASE_INTERNAL = resolveBaseUrl(import.meta.env.VITE_API_BASE_URL);
const BACKEND_PORTAL_INTERNAL = resolveBaseUrl(
  import.meta.env.VITE_BACKEND_PORTAL_URL,
  import.meta.env.VITE_API_BASE_URL
);

const API_BASE = displayBaseUrl(API_BASE_INTERNAL);
const BACKEND_PORTAL = displayBaseUrl(BACKEND_PORTAL_INTERNAL);

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

async function request<T>(path: string, method: Method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(joinBaseAndPath(API_BASE_INTERNAL, path), {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { error?: string }).error || `Request failed: ${res.status}`);
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, "GET"),
  post: <T>(path: string, body?: unknown) => request<T>(path, "POST", body),
};

function buildApiUrl(path: string) {
  return joinBaseAndPath(API_BASE_INTERNAL, path);
}

function buildBackendUrl(path: string) {
  return joinBaseAndPath(BACKEND_PORTAL_INTERNAL, path);
}

export { API_BASE, BACKEND_PORTAL, buildApiUrl, buildBackendUrl };
