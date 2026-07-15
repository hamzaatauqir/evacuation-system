/**
 * Pure-logic tests for the React homepage advertisement (src/lib/homepageAds.ts).
 *
 * Mirrors tests/smoke/site_ads_logic.mjs, which covers the Flask equivalent —
 * the two implementations must agree on dismissal keys, display frequency and
 * CTA URL safety, because both write the same browser storage keys.
 *
 * Usage: node --experimental-strip-types scripts/homepageAdsSmoke.ts
 */
import {
  type AdPopup,
  LONG_TEXT_THRESHOLD,
  PUBLIC_ADS_ENDPOINT,
  bannerDismissalKey,
  ctaAttributes,
  popupDismissalKey,
  shouldCollapseDetails,
  shouldShowPopup,
  telHref,
} from "../src/lib/homepageAds.ts";

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

const HOUR = 3600000;
const popup = (over: Partial<AdPopup> = {}) =>
  ({
    id: 1,
    v: 1,
    frequency: "once_per_version",
    dismissalHours: 168,
    image: "https://evacuation-system.onrender.com/ads/media/a.png",
    description: "",
    descriptionUr: "",
    ...over,
  }) as AdPopup;

console.log("Test 1: endpoint contract");
assertEqual("public endpoint path", PUBLIC_ADS_ENDPOINT, "/api/public/advertisements/active");

console.log("Test 2: dismissal keys match the Flask implementation");
assertEqual("popup key format", popupDismissalKey(3, 2), "cwa_ad_dismissed:3:2");
assertEqual("banner key format", bannerDismissalKey(3, 2), "cwa_ad_banner_dismissed:3:2");
check("popup and banner keys differ", popupDismissalKey(3, 2) !== bannerDismissalKey(3, 2));
check("new content version changes the key", popupDismissalKey(3, 2) !== popupDismissalKey(3, 3));

console.log("Test 3: shouldShowPopup — content_version invalidation");
check("no popup -> false", shouldShowPopup(null, {}) === false);
check("never dismissed -> show", shouldShowPopup(popup(), { localValue: null }) === true);
check(
  "recently dismissed -> hide",
  shouldShowPopup(popup(), { localValue: String(Date.now()), now: Date.now() }) === false
);
check(
  "dismissal window elapsed -> show again",
  shouldShowPopup(popup({ dismissalHours: 1 }), {
    localValue: String(Date.now() - 2 * HOUR),
    now: Date.now(),
  }) === true
);
check(
  "dismissalHours 0 -> never re-show this version",
  shouldShowPopup(popup({ dismissalHours: 0 }), { localValue: String(Date.now()), now: Date.now() }) === false
);
check(
  "corrupt storage value -> show",
  shouldShowPopup(popup(), { localValue: "not-a-number" }) === true
);

console.log("Test 4: display frequencies");
check("every_visit always shows", shouldShowPopup(popup({ frequency: "every_visit" }), { localValue: String(Date.now()) }) === true);
check("once_per_session hides with session value", shouldShowPopup(popup({ frequency: "once_per_session" }), { sessionValue: "1" }) === false);
check("once_per_session shows without session value", shouldShowPopup(popup({ frequency: "once_per_session" }), { sessionValue: null }) === true);
check("once_per_session ignores local dismissal", shouldShowPopup(popup({ frequency: "once_per_session" }), { sessionValue: null, localValue: String(Date.now()) }) === true);

console.log("Test 5: ctaAttributes — admin URL safety");
check("javascript: refused", ctaAttributes("javascript:alert(1)", true, "cwakuwait.com") === null);
check("data: refused", ctaAttributes("data:text/html,x", true, "cwakuwait.com") === null);
check("http: refused", ctaAttributes("http://x.dev", true, "cwakuwait.com") === null);
check("protocol-relative refused", ctaAttributes("//evil.dev", true, "cwakuwait.com") === null);
check("embedded credentials refused", ctaAttributes("https://user@evil.dev", true, "cwakuwait.com") === null);
check("empty refused", ctaAttributes("", true, "cwakuwait.com") === null);
assertEqual("internal path allowed", ctaAttributes("/nurses", false, "cwakuwait.com")?.href, "/nurses");
check("internal path is not external", ctaAttributes("/nurses", false, "cwakuwait.com")?.external === false);
check("https other host is external", ctaAttributes("https://who.int", true, "cwakuwait.com")?.external === true);
check("https same host is internal", ctaAttributes("https://cwakuwait.com/x", true, "cwakuwait.com")?.external === false);
assertEqual("new tab sets target", ctaAttributes("https://who.int", true, "cwakuwait.com")?.target, "_blank");
assertEqual("new tab sets rel", ctaAttributes("https://who.int", true, "cwakuwait.com")?.rel, "noopener noreferrer");
assertEqual("same tab has no target", ctaAttributes("https://who.int", false, "cwakuwait.com")?.target, "");

console.log("Test 6: telHref");
assertEqual("formats digits", telHref("+965 5597 7292"), "tel:+96555977292");
assertEqual("too short -> empty", telHref("12"), "");
assertEqual("empty -> empty", telHref(""), "");

console.log("Test 7: shouldCollapseDetails — duplicate poster text");
const longText = "x".repeat(LONG_TEXT_THRESHOLD + 1);
check("long description with poster collapses", shouldCollapseDetails(popup({ description: longText })) === true);
check("short description stays expanded (backwards compatible)", shouldCollapseDetails(popup({ description: "Short notice." })) === false);
check("no poster never collapses", shouldCollapseDetails(popup({ image: "", description: longText })) === false);
check("combined en+ur length counts", shouldCollapseDetails(popup({ description: "x".repeat(200), descriptionUr: "ی".repeat(200) })) === true);
check("null popup -> false", shouldCollapseDetails(null) === false);

console.log("");
if (failures.length) {
  console.log(`FAILED  ${failures.length} check(s): ${failures.join(", ")}`);
  process.exit(1);
}
console.log(`OK  ${passes} checks passed`);
