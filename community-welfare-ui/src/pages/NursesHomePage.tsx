import { useNavigate } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { HeroCarousel } from "../components/HeroCarousel";
import { NoticeCard } from "../components/NoticeCard";
import { ServiceCard } from "../components/ServiceCard";
import { Section, SecTitle } from "../components/Layout";
import { ProcessSteps } from "../components/ProcessSteps";
import { ContactCard } from "../components/ContactCard";
import { PageFooter } from "../components/PageFooter";
import { T } from "../lib/tokens";
import type { IconName } from "../components/Icon";

type Variant = "primary" | "navy" | "secondary" | "ghost" | "danger" | "light";

interface ServiceDef {
  icon: IconName;
  title: string;
  desc: string;
  cta: string;
  ctaVariant: Variant;
  accent: string;
  to: string;
}

export function NursesHomePage() {
  const navigate = useNavigate();
  const cards: ServiceDef[] = [
    {
      icon: "user-add",
      title: "New Nurses Registration",
      desc: "Initial registration for newly arrived Pakistani nursing staff in the State of Kuwait.",
      cta: "Register Now",
      ctaVariant: "primary",
      accent: T.green,
      to: "/nurses/register",
    },
    {
      icon: "user",
      title: "Existing Nurse Login / Track",
      desc: "Access your portal to update details or monitor the progress of your registration and requests.",
      cta: "Login / Track",
      ctaVariant: "navy",
      accent: T.navy,
      to: "/nurses/login",
    },
    {
      icon: "home",
      title: "Accommodation Request",
      desc: "Submit requests for MOH or private hospital accommodation-related facilitation and placement.",
      cta: "Apply Now",
      ctaVariant: "secondary",
      accent: "#0369a1",
      to: "/nurses/accommodation",
    },
    {
      icon: "alert",
      title: "Complaint / Welfare Issue",
      desc: "Report workplace grievances, administrative issues, or urgent welfare concerns to the Embassy.",
      cta: "Report Issue",
      ctaVariant: "secondary",
      accent: T.error,
      to: "/nurses/complaint",
    },
    {
      icon: "exit",
      title: "Leaving Notice / Exit",
      desc: "Submit official notification before vacating Embassy or hospital-provided accommodation.",
      cta: "Submit Notice",
      ctaVariant: "secondary",
      accent: "#92400e",
      to: "/nurses/leaving-notice",
    },
  ];

  const steps = [
    { title: "Register / Login", desc: "Create or access your account using your Civil ID and Passport." },
    { title: "Submit Request", desc: "Fill out the relevant service form with your details." },
    { title: "Embassy Review", desc: "Community Welfare Wing officers verify your information." },
    { title: "Track Status", desc: "Receive updates or check status on your dashboard." },
  ];

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />

      {/* Hero */}
      <section
        style={{
          background: "linear-gradient(160deg,#2D4A6B 0%,#3A6080 100%)",
          padding: "72px 24px 64px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage:
              "radial-gradient(ellipse at 70% 40%,rgba(47,125,78,.15) 0%,transparent 55%)",
            pointerEvents: "none",
          }}
        />
        <div
          style={{
            maxWidth: 1200,
            margin: "0 auto",
            position: "relative",
            zIndex: 1,
            display: "flex",
            alignItems: "center",
            gap: 48,
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: "1 1 340px", maxWidth: 540 }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: "rgba(255,255,255,.1)",
                border: "1px solid rgba(255,255,255,.18)",
                borderRadius: 20,
                padding: "5px 14px",
                fontSize: 11,
                fontWeight: 700,
                color: "rgba(255,255,255,.88)",
                marginBottom: 22,
                letterSpacing: ".05em",
              }}
            >
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#6ee79a" }} />
              NURSES PORTAL
            </div>
            <h1
              style={{
                fontSize: "clamp(24px,3.5vw,44px)",
                fontWeight: 800,
                color: "#fff",
                lineHeight: 1.2,
                marginBottom: 14,
              }}
            >
              Pakistan Nurses
              <br />
              <span style={{ color: "#9cf987" }}>Registration Portal</span>
            </h1>
            <p
              style={{
                fontSize: 14,
                color: "rgba(255,255,255,.68)",
                maxWidth: 460,
                lineHeight: 1.75,
                marginBottom: 22,
              }}
            >
              Dedicated Community Welfare Wing portal for Pakistani nurses in Kuwait. Ensuring streamlined
              support, housing coordination, and welfare management.
            </p>
            <NoticeCard type="info">
              <strong>Important:</strong> This nurses portal is separate from KSA transit visa applications.
              No document uploads required — supporting docs requested by official email only.
            </NoticeCard>
          </div>
          <div style={{ flex: "1 1 300px", maxWidth: 420 }}>
            <HeroCarousel inline caption="Embassy of Pakistan, Kuwait — Community Welfare Wing" />
          </div>
        </div>
      </section>

      <main style={{ flex: 1 }}>
        {/* Service cards */}
        <Section bg={T.bg}>
          <SecTitle
            title="Nurses Welfare Services"
            sub="Select the relevant service to submit your request or track an existing application."
            center
          />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(255px,1fr))",
              gap: 18,
            }}
          >
            {cards.map((c) => (
              <ServiceCard
                key={c.title}
                icon={c.icon}
                title={c.title}
                desc={c.desc}
                cta={c.cta}
                ctaVariant={c.ctaVariant}
                accent={c.accent}
                onClick={() => navigate(c.to)}
              />
            ))}
          </div>
        </Section>

        {/* Process */}
        <Section bg={T.surfaceLow}>
          <SecTitle title="Service Delivery Process" center />
          <ProcessSteps steps={steps} />
        </Section>

        {/* Contact */}
        <Section bg={T.bg} style={{ paddingTop: 0 }}>
          <ContactCard
            email="parepkuwaitcwa37@gmail.com"
            phone="+965 5597 7292"
            hours="Sunday – Thursday, 8:00 AM – 3:30 PM (Kuwait Time)"
          />
        </Section>
      </main>

      <PageFooter />
    </div>
  );
}
