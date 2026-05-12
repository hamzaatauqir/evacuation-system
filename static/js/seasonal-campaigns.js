(function (root, factory) {
  const api = factory();

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  root.CwaSeasonalCampaigns = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const INTERNATIONAL_NURSES_DAY_CAMPAIGN_TIMEZONE = "Asia/Kuwait";

  // Temporary date-controlled campaign window. Update these values for the
  // next Nurses Day campaign instead of removing the homepage/login markup.
  const INTERNATIONAL_NURSES_DAY_CAMPAIGN_START = "2026-05-12T00:00:00+03:00";
  const INTERNATIONAL_NURSES_DAY_CAMPAIGN_END = "2026-05-16T00:00:00+03:00";

  function toTimestamp(value) {
    if (value === undefined || value === null || value === "") {
      return NaN;
    }
    if (value instanceof Date) {
      return value.getTime();
    }
    if (typeof value === "number") {
      return value;
    }
    return new Date(value).getTime();
  }

  function isDateWindowActive(now, start, end) {
    const nowMs = toTimestamp(now === undefined ? new Date() : now);
    const startMs = toTimestamp(start);
    const endMs = toTimestamp(end);

    if (!Number.isFinite(nowMs) || !Number.isFinite(startMs) || !Number.isFinite(endMs)) {
      return false;
    }

    return nowMs >= startMs && nowMs < endMs;
  }

  function isInternationalNursesDayCampaignActive(now) {
    return isDateWindowActive(
      now,
      INTERNATIONAL_NURSES_DAY_CAMPAIGN_START,
      INTERNATIONAL_NURSES_DAY_CAMPAIGN_END
    );
  }

  function getInternationalNursesDayGreetingSalutation(name) {
    const trimmed = String(name || "").trim();
    return trimmed ? "Dear " + trimmed + "," : "Dear Nurse,";
  }

  return Object.freeze({
    INTERNATIONAL_NURSES_DAY_CAMPAIGN_TIMEZONE,
    INTERNATIONAL_NURSES_DAY_CAMPAIGN_START,
    INTERNATIONAL_NURSES_DAY_CAMPAIGN_END,
    isDateWindowActive,
    isInternationalNursesDayCampaignActive,
    getInternationalNursesDayGreetingSalutation,
  });
});
