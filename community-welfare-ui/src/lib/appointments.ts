// Online appointment booking for Embassy counter services.
//
// The booking system runs on a separate host (service.cwakuwait.com) and is not
// part of this React app — the public site only links out to it. This module is
// the single source of truth for that target URL and for the service list and
// attendance guidance shown on the homepage, so copy never drifts between the
// hero CTA and the appointment section.

export const EMBASSY_APPOINTMENT_URL =
  "https://service.cwakuwait.com/appointments/language.html";

// Languages offered by the booking system's first (language selection) screen.
export const EMBASSY_APPOINTMENT_LANGUAGES = ["English", "اردو", "العربية"] as const;

export interface AppointmentService {
  title: string;
  desc: string;
}

export const EMBASSY_APPOINTMENT_SERVICES: AppointmentService[] = [
  {
    title: "NADRA",
    desc: "CNIC / NICOP applications, renewals and modifications, and family registration certificates.",
  },
  {
    title: "Passport",
    desc: "New passports, renewals, and collection of a passport at the Embassy passport counter.",
  },
  {
    title: "Community Welfare (CWA) Wing",
    desc: "Labour and welfare matters, community complaints, grading letters, and welfare assistance.",
  },
  {
    title: "Counsellor Section",
    desc: "Attestation of documents, powers of attorney, and other consular / counsellor services.",
  },
];

export const APPOINTMENT_PURPOSE_NOTE =
  "Booking online reserves your turn in advance so you spend less time waiting at the Embassy.";

export const APPOINTMENT_ARRIVAL_NOTE =
  "Please reach the Embassy at the right time — your slot is held only for its scheduled appointment time. If you miss it, the appointment has to be booked again.";

export const APPOINTMENT_WAITING_NOTE =
  "Even with a confirmed appointment, please allow a waiting time of up to about 30 minutes, depending on the case of the person next in line.";

/**
 * Opens the external booking system in a new tab.
 *
 * Kept as a helper (rather than an inline `window.open`) so every entry point on
 * the site opens the same URL with the same `noopener` protection. Falls back to
 * a same-tab navigation if the popup is blocked.
 */
export function openAppointmentBooking() {
  if (typeof window === "undefined") return;
  const opened = window.open(EMBASSY_APPOINTMENT_URL, "_blank", "noopener,noreferrer");
  if (!opened) {
    window.location.assign(EMBASSY_APPOINTMENT_URL);
  }
}
