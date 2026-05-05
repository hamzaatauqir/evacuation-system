function isLocalhostUrl(value: string) {
  return /^https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?$/i.test(value.trim());
}

function browserOrigin() {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "http://localhost:8080";
}

function resolveBaseUrl(primary?: string, fallback?: string) {
  const candidate = (primary || fallback || "").trim();
  if (candidate && !(import.meta.env.PROD && isLocalhostUrl(candidate))) {
    return candidate;
  }
  return browserOrigin();
}

const API_BASE = resolveBaseUrl(import.meta.env.VITE_API_BASE_URL);
const BACKEND_PORTAL = resolveBaseUrl(
  import.meta.env.VITE_BACKEND_PORTAL_URL,
  import.meta.env.VITE_API_BASE_URL
);

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

async function request<T>(path: string, method: Method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
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

export { API_BASE, BACKEND_PORTAL };
