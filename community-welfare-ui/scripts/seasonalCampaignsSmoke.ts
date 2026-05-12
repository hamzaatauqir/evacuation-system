import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  INTERNATIONAL_NURSES_DAY_CAMPAIGN_END,
  INTERNATIONAL_NURSES_DAY_CAMPAIGN_START,
  isInternationalNursesDayCampaignActive,
} from "../src/lib/seasonalCampaigns.ts";

const scriptsDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptsDir, "..");

let failures = 0;

function assertEqual(label: string, got: unknown, expected: unknown) {
  if (got !== expected) {
    console.log(`FAIL ${label}: got=${JSON.stringify(got)} expected=${JSON.stringify(expected)}`);
    failures += 1;
    return;
  }
  console.log(`PASS ${label}`);
}

function assertTrue(label: string, value: boolean) {
  assertEqual(label, value, true);
}

console.log("Test 1: campaign window constants");
assertEqual("start constant", INTERNATIONAL_NURSES_DAY_CAMPAIGN_START, "2026-05-12T00:00:00+03:00");
assertEqual("end constant", INTERNATIONAL_NURSES_DAY_CAMPAIGN_END, "2026-05-16T00:00:00+03:00");

console.log("");
console.log("Test 2: campaign active window");
assertEqual("active on campaign start", isInternationalNursesDayCampaignActive("2026-05-12T00:00:00+03:00"), true);
assertEqual("active on May 15 evening Kuwait time", isInternationalNursesDayCampaignActive("2026-05-15T23:59:59+03:00"), true);

console.log("");
console.log("Test 3: campaign inactive outside window");
assertEqual("inactive before campaign", isInternationalNursesDayCampaignActive("2026-05-11T23:59:59+03:00"), false);
assertEqual("inactive from May 16 onward", isInternationalNursesDayCampaignActive("2026-05-16T00:00:00+03:00"), false);

console.log("");
console.log("Test 4: homepage/login/portal integration");
const homepageSource = readFileSync(resolve(projectRoot, "src/pages/CwaHomePage.tsx"), "utf8");
const loginSource = readFileSync(resolve(projectRoot, "src/pages/NursesLoginPage.tsx"), "utf8");
const portalSource = readFileSync(resolve(projectRoot, "src/pages/NursesPortalPage.tsx"), "utf8");
const cardSource = readFileSync(resolve(projectRoot, "src/components/InternationalNursesDayCampaignCard.tsx"), "utf8");

assertTrue(
  "homepage gates banner by campaign helper",
  homepageSource.includes("isInternationalNursesDayCampaignActive") &&
    homepageSource.includes('variant="homepage"')
);
assertTrue(
  "login page gates welcome card by campaign helper",
  loginSource.includes("isInternationalNursesDayCampaignActive") &&
    loginSource.includes('variant="welcome"')
);
assertTrue(
  "portal page gates welcome card by campaign helper",
  portalSource.includes("isInternationalNursesDayCampaignActive") &&
    portalSource.includes('variant="welcome"')
);
assertTrue(
  "campaign card includes required homepage CTA and theme",
  cardSource.includes("Open Nurses Portal") &&
    cardSource.includes("Our Nurses. Our Future.") &&
    cardSource.includes("Empowered Nurses Save Lives.")
);

console.log("");
console.log(`FAIL count: ${failures}`);
process.exit(failures === 0 ? 0 : 1);
