import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  APPOINTMENT_ARRIVAL_NOTE,
  APPOINTMENT_WAITING_NOTE,
  EMBASSY_APPOINTMENT_LANGUAGES,
  EMBASSY_APPOINTMENT_SERVICES,
  EMBASSY_APPOINTMENT_URL,
} from "../src/lib/appointments.ts";

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

console.log("Test 1: booking URL constant");
assertEqual(
  "points at the live appointment system",
  EMBASSY_APPOINTMENT_URL,
  "https://service.cwakuwait.com/appointments/language.html"
);
assertTrue("uses https", EMBASSY_APPOINTMENT_URL.startsWith("https://"));

console.log("");
console.log("Test 2: advertised service list");
const titles = EMBASSY_APPOINTMENT_SERVICES.map((s) => s.title);
assertEqual("four services listed", titles.length, 4);
assertTrue("NADRA listed", titles.some((t) => t.includes("NADRA")));
assertTrue("Passport listed", titles.some((t) => t.includes("Passport")));
assertTrue("CWA Wing listed", titles.some((t) => t.includes("CWA")));
assertTrue("Counsellor Section listed", titles.some((t) => t.includes("Counsellor")));
assertTrue(
  "every service has a description",
  EMBASSY_APPOINTMENT_SERVICES.every((s) => s.desc.trim().length > 0)
);

console.log("");
console.log("Test 3: attendance guidance copy");
assertTrue("arrival note tells applicants to reach on time", APPOINTMENT_ARRIVAL_NOTE.includes("right time"));
assertTrue("arrival note warns about missing the slot", APPOINTMENT_ARRIVAL_NOTE.includes("miss"));
assertTrue("waiting note states the 30 minute expectation", APPOINTMENT_WAITING_NOTE.includes("30 minutes"));
assertTrue("waiting note explains the cause", APPOINTMENT_WAITING_NOTE.includes("next in line"));
assertEqual("three booking languages advertised", EMBASSY_APPOINTMENT_LANGUAGES.length, 3);

console.log("");
console.log("Test 4: homepage integration");
const homepageSource = readFileSync(resolve(projectRoot, "src/pages/CwaHomePage.tsx"), "utf8");
const cardSource = readFileSync(resolve(projectRoot, "src/components/AppointmentBookingCard.tsx"), "utf8");

assertTrue(
  "homepage renders the appointment card",
  homepageSource.includes("AppointmentBookingCard")
);
assertTrue(
  "homepage hero exposes a booking CTA",
  homepageSource.includes("openAppointmentBooking") && homepageSource.includes("Book an Appointment")
);
assertTrue(
  "card links out via a real anchor opened in a new tab",
  cardSource.includes("EMBASSY_APPOINTMENT_URL") &&
    cardSource.includes('target="_blank"') &&
    cardSource.includes('rel="noopener noreferrer"')
);
assertTrue(
  "card copy comes from the shared module, not hardcoded strings",
  cardSource.includes("EMBASSY_APPOINTMENT_SERVICES") &&
    cardSource.includes("APPOINTMENT_ARRIVAL_NOTE") &&
    cardSource.includes("APPOINTMENT_WAITING_NOTE")
);
assertTrue(
  "card carries the required heading",
  cardSource.includes("Online Appointment for Embassy Services")
);
assertTrue(
  "no hardcoded booking URL leaks into the homepage",
  !homepageSource.includes("service.cwakuwait.com")
);

console.log("");
console.log(`FAIL count: ${failures}`);
process.exit(failures === 0 ? 0 : 1);
