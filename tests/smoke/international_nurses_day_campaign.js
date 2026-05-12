#!/usr/bin/env node
// Smoke coverage for the temporary International Nurses Day campaign window.

const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");
const helper = require(path.join(repoRoot, "static/js/seasonal-campaigns.js"));

let failures = 0;

function assertEq(label, got, expected) {
  if (got !== expected) {
    console.log("  FAIL " + label + ": got=" + JSON.stringify(got) + " expected=" + JSON.stringify(expected));
    failures += 1;
    return;
  }
  console.log("  PASS " + label);
}

console.log("Test 1: campaign constants");
assertEq(
  "start constant",
  helper.INTERNATIONAL_NURSES_DAY_CAMPAIGN_START,
  "2026-05-12T00:00:00+03:00"
);
assertEq(
  "end constant",
  helper.INTERNATIONAL_NURSES_DAY_CAMPAIGN_END,
  "2026-05-16T00:00:00+03:00"
);

console.log("");
console.log("Test 2: active window");
assertEq(
  "active on campaign start",
  helper.isInternationalNursesDayCampaignActive("2026-05-12T00:00:00+03:00"),
  true
);
assertEq(
  "active on May 15 evening Kuwait time",
  helper.isInternationalNursesDayCampaignActive("2026-05-15T23:59:59+03:00"),
  true
);

console.log("");
console.log("Test 3: inactive outside the window");
assertEq(
  "inactive before campaign",
  helper.isInternationalNursesDayCampaignActive("2026-05-11T23:59:59+03:00"),
  false
);
assertEq(
  "inactive after campaign end",
  helper.isInternationalNursesDayCampaignActive("2026-05-16T00:00:00+03:00"),
  false
);

console.log("");
console.log("Test 4: templates stay hidden by default");
const homeTemplate = fs.readFileSync(path.join(repoRoot, "templates/cwa_home.html"), "utf8");
const nursesTemplate = fs.readFileSync(path.join(repoRoot, "templates/nurses_login.html"), "utf8");
assertEq(
  "homepage banner hidden attribute present",
  /id="internationalNursesDayBanner"[\s\S]*?\shidden(?:[\s>])/.test(homeTemplate),
  true
);
assertEq(
  "nurses greeting hidden attribute present",
  /id="nursesDayLoginGreeting"[\s\S]*?\shidden(?:[\s>])/.test(nursesTemplate),
  true
);

console.log("");
console.log("FAIL count: " + failures);
process.exit(failures === 0 ? 0 : 1);
