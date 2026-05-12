export type CampaignDateInput = Date | string | number;

export const INTERNATIONAL_NURSES_DAY_CAMPAIGN_BADGE = "International Nurses Day 2026";

// Temporary date-controlled campaign window for the public frontend.
// Update these constants for future Nurses Day campaigns instead of
// removing the homepage / nurse-portal greeting components.
export const INTERNATIONAL_NURSES_DAY_CAMPAIGN_START = "2026-05-12T00:00:00+03:00";
export const INTERNATIONAL_NURSES_DAY_CAMPAIGN_END = "2026-05-16T00:00:00+03:00";

function toTimestamp(value: CampaignDateInput | undefined) {
  if (value == null || value === "") return Number.NaN;
  if (value instanceof Date) return value.getTime();
  if (typeof value === "number") return value;
  return new Date(value).getTime();
}

export function isDateWindowActive(
  now: CampaignDateInput = new Date(),
  start: CampaignDateInput,
  end: CampaignDateInput
) {
  const nowMs = toTimestamp(now);
  const startMs = toTimestamp(start);
  const endMs = toTimestamp(end);

  if (![nowMs, startMs, endMs].every(Number.isFinite)) {
    return false;
  }

  return nowMs >= startMs && nowMs < endMs;
}

export function isInternationalNursesDayCampaignActive(now: CampaignDateInput = new Date()) {
  return isDateWindowActive(
    now,
    INTERNATIONAL_NURSES_DAY_CAMPAIGN_START,
    INTERNATIONAL_NURSES_DAY_CAMPAIGN_END
  );
}

export function getInternationalNursesDayGreetingSalutation(name?: string | null) {
  const trimmed = String(name || "").trim();
  return trimmed ? `Dear ${trimmed},` : "Dear Nurse,";
}
