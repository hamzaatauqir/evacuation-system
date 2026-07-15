/**
 * Regression tests for backend-origin resolution.
 *
 * The bug these lock down: index.html used Vite's %VITE_X% HTML substitution
 * and compared the substituted value against a sentinel written as that same
 * placeholder token. The build rewrote both sides to the same string, so the
 * comparison always matched, every configured backend URL was discarded, and
 * the code fell through to the retired portal.cwakuwait.com host (403).
 *
 * Usage: node --experimental-strip-types scripts/apiBaseSmoke.ts
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  DEFAULT_PUBLIC_BACKEND_ORIGIN,
  firstConfiguredOrigin,
  isDeprecatedPortalOrigin,
  isSelfReferentialTarget,
  isUnreplacedPlaceholder,
  joinBaseAndPath,
  resolveApiBaseUrl,
  resolvePublicBackendPortal,
  sanitizeConfiguredOrigin,
} from "../src/lib/backendOrigin.ts";

const scriptsDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptsDir, "..");

const BACKEND = "https://evacuation-system.onrender.com";
let passes = 0;
const failures: string[] = [];

function check(name: string, ok: boolean, detail = "") {
  if (ok) {
    passes += 1;
    console.log(`  PASS  ${name}`);
  } else {
    failures.push(name);
    console.log(`  FAIL  ${name} ${detail}`);
  }
}

function assertEqual(name: string, got: unknown, expected: unknown) {
  check(name, got === expected, `got=${JSON.stringify(got)} expected=${JSON.stringify(expected)}`);
}

console.log("Test 1: unreplaced placeholder detection");
check("bare placeholder is unreplaced", isUnreplacedPlaceholder("%VITE_API_BASE_URL%"));
check("portal placeholder is unreplaced", isUnreplacedPlaceholder("%VITE_BACKEND_PORTAL_URL%"));
check("real url is not a placeholder", !isUnreplacedPlaceholder(BACKEND));
check("empty is not a placeholder", !isUnreplacedPlaceholder(""));
check("percent-in-path is not a placeholder", !isUnreplacedPlaceholder("https://x.dev/a%20b"));

console.log("Test 2: sanitizeConfiguredOrigin");
assertEqual("configured backend survives", sanitizeConfiguredOrigin(BACKEND), BACKEND);
assertEqual("trailing slash trimmed", sanitizeConfiguredOrigin(`${BACKEND}/`), BACKEND);
assertEqual("unreplaced placeholder -> empty", sanitizeConfiguredOrigin("%VITE_API_BASE_URL%"), "");
assertEqual("retired portal -> empty", sanitizeConfiguredOrigin("https://portal.cwakuwait.com"), "");
assertEqual("empty -> empty", sanitizeConfiguredOrigin(""), "");
check("portal host detected", isDeprecatedPortalOrigin("https://portal.cwakuwait.com/x"));

console.log("Test 3: THE REGRESSION — configured origin survives the build");
// Before the fix these two arguments were identical strings, so the guard
// treated the real value as the sentinel and returned "".
assertEqual("backend wins over placeholder fallback", firstConfiguredOrigin(BACKEND, "%VITE_API_BASE_URL%"), BACKEND);
assertEqual("placeholder primary falls through to real fallback", firstConfiguredOrigin("%VITE_BACKEND_PORTAL_URL%", BACKEND), BACKEND);
assertEqual("both placeholders -> empty", firstConfiguredOrigin("%VITE_BACKEND_PORTAL_URL%", "%VITE_API_BASE_URL%"), "");

console.log("Test 4: resolvePublicBackendPortal (/register, /apply, /transit)");
assertEqual(
  "configured API base is used on cwakuwait.com",
  resolvePublicBackendPortal({ VITE_API_BASE_URL: BACKEND }, { hostname: "cwakuwait.com", origin: "https://cwakuwait.com" }),
  BACKEND
);
assertEqual(
  "explicit portal override wins",
  resolvePublicBackendPortal({ VITE_BACKEND_PORTAL_URL: "https://alt.example.com", VITE_API_BASE_URL: BACKEND }, { hostname: "cwakuwait.com" }),
  "https://alt.example.com"
);
assertEqual(
  "unconfigured cwakuwait.com no longer resolves to the retired portal",
  resolvePublicBackendPortal({}, { hostname: "cwakuwait.com", origin: "https://cwakuwait.com" }),
  DEFAULT_PUBLIC_BACKEND_ORIGIN
);
check(
  "default is never the retired portal",
  !isDeprecatedPortalOrigin(DEFAULT_PUBLIC_BACKEND_ORIGIN)
);
assertEqual(
  "configured retired portal is ignored, not honoured",
  resolvePublicBackendPortal({ VITE_API_BASE_URL: "https://portal.cwakuwait.com" }, { hostname: "www.cwakuwait.com", origin: "https://www.cwakuwait.com" }),
  DEFAULT_PUBLIC_BACKEND_ORIGIN
);
assertEqual(
  "localhost dev resolves to :8080",
  resolvePublicBackendPortal({}, { protocol: "http:", hostname: "localhost", port: "5173", origin: "http://localhost:5173" }),
  "http://localhost:8080"
);

console.log("Test 5: resolveApiBaseUrl (api.ts)");
assertEqual(
  "prod uses configured absolute backend",
  resolveApiBaseUrl(BACKEND, undefined, { PROD: true }, { hostname: "cwakuwait.com", origin: "https://cwakuwait.com" }),
  BACKEND
);
assertEqual(
  "prod placeholder falls back to same-origin",
  resolveApiBaseUrl("%VITE_API_BASE_URL%", undefined, { PROD: true }, { hostname: "cwakuwait.com", origin: "https://cwakuwait.com" }),
  ""
);
assertEqual(
  "prod ignores a localhost base",
  resolveApiBaseUrl("http://localhost:8080", undefined, { PROD: true }, { hostname: "cwakuwait.com", origin: "https://cwakuwait.com" }),
  ""
);

console.log("Test 6: joinBaseAndPath builds the ads endpoint");
assertEqual(
  "ads endpoint is absolute against the backend",
  joinBaseAndPath(BACKEND, "/api/public/advertisements/active"),
  `${BACKEND}/api/public/advertisements/active`
);
assertEqual("empty base -> relative", joinBaseAndPath("", "/api/x"), "/api/x");

console.log("Test 7: alias redirect cannot loop");
check(
  "same-origin same-path target is refused",
  isSelfReferentialTarget("https://cwakuwait.com/embassy-registration", {
    origin: "https://cwakuwait.com",
    pathname: "/embassy-registration",
  })
);
check(
  "cross-origin target is allowed",
  !isSelfReferentialTarget(`${BACKEND}/embassy-registration`, {
    origin: "https://cwakuwait.com",
    pathname: "/embassy-registration",
  })
);

console.log("Test 8: index.html source does not reintroduce the sentinel bug");
const html = readFileSync(resolve(projectRoot, "index.html"), "utf8");
check(
  "no equality comparison against a %VITE_% placeholder literal",
  !/===\s*"%VITE_[A-Z_]+%"/.test(html) && !/"%VITE_[A-Z_]+%"\s*===/.test(html),
  "index.html compares a value against a placeholder literal; the build rewrites both sides"
);
check("index.html no longer defaults to the retired portal", !/backend\s*=\s*"https:\/\/portal\.cwakuwait\.com"/.test(html));
check("index.html reads the env placeholders", html.includes("%VITE_API_BASE_URL%"));

console.log("");
if (failures.length) {
  console.log(`FAILED  ${failures.length} check(s): ${failures.join(", ")}`);
  process.exit(1);
}
console.log(`OK  ${passes} checks passed`);
