import { INTERNATIONAL_NURSES_DAY_CAMPAIGN_BADGE, getInternationalNursesDayGreetingSalutation } from "../lib/seasonalCampaigns";

type InternationalNursesDayCampaignCardProps = {
  variant: "homepage" | "welcome";
  recipientName?: string | null;
  portalHref?: string;
};

export function InternationalNursesDayCampaignCard({
  variant,
  recipientName,
  portalHref = "/nurses/login",
}: InternationalNursesDayCampaignCardProps) {
  if (variant === "homepage") {
    return (
      <section className="cwa-campaign-card cwa-campaign-card--homepage" aria-label="International Nurses Day campaign banner">
        <div className="cwa-campaign-card__content">
          <span className="cwa-campaign-card__badge">{INTERNATIONAL_NURSES_DAY_CAMPAIGN_BADGE}</span>
          <h2 className="cwa-campaign-card__title">Happy International Nurses Day</h2>
          <div className="cwa-campaign-card__body">
            <p>
              The Community Welfare Wing, Embassy of Pakistan in Kuwait, extends warm greetings and sincere
              appreciation to all nurses serving with dedication, compassion, and professionalism.
            </p>
            <p>
              On this special occasion, we especially recognize the valuable contribution of Pakistani nurses in
              Kuwait, whose service reflects the best values of care, humanity, and commitment.
            </p>
          </div>
          <div className="cwa-campaign-card__theme">
            <strong>Our Nurses. Our Future.</strong>
            <span>Empowered Nurses Save Lives.</span>
          </div>
        </div>
        <div className="cwa-campaign-card__actions">
          <a className="cwa-campaign-card__cta" href={portalHref}>
            Open Nurses Portal
          </a>
        </div>
      </section>
    );
  }

  return (
    <section className="cwa-campaign-card cwa-campaign-card--welcome" aria-label="International Nurses Day welcome message">
      <div className="cwa-campaign-card__content">
        <span className="cwa-campaign-card__badge">{INTERNATIONAL_NURSES_DAY_CAMPAIGN_BADGE}</span>
        <h2 className="cwa-campaign-card__title">Happy International Nurses Day</h2>
        <div className="cwa-campaign-card__body">
          <p>{getInternationalNursesDayGreetingSalutation(recipientName)}</p>
          <p>
            The Community Welfare Wing, Embassy of Pakistan in Kuwait, extends heartfelt greetings and sincere
            appreciation to you on International Nurses Day.
          </p>
          <p>
            Your dedication, compassion, discipline, and professional commitment are a source of pride for Pakistan
            and a valuable contribution to the healthcare sector of Kuwait.
          </p>
          <p>
            We wish you continued success, good health, professional growth, and happiness in your noble service to
            humanity.
          </p>
        </div>
        <p className="cwa-campaign-card__signature">
          With best wishes,
          <br />
          Community Welfare Wing
          <br />
          Embassy of Pakistan, Kuwait
        </p>
      </div>
    </section>
  );
}
