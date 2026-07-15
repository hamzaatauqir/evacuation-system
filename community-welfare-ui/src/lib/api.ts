/**
 * API client. Backend-origin resolution lives in ./backendOrigin — do not
 * reintroduce a second copy here; three call sites disagreeing is what broke
 * the production API base.
 */
import { joinBaseAndPath, resolveApiBaseUrl, viteEnv } from "./backendOrigin";

function displayBaseUrl(base: string) {
  if (base) return base;
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "this site";
}

const API_BASE_INTERNAL = resolveApiBaseUrl(viteEnv().VITE_API_BASE_URL);
const BACKEND_PORTAL_INTERNAL = resolveApiBaseUrl(
  viteEnv().VITE_BACKEND_PORTAL_URL,
  viteEnv().VITE_API_BASE_URL
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
