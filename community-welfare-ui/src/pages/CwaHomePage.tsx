import { useNavigate } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { HeroCarousel } from "../components/HeroCarousel";
import { ServiceCard } from "../components/ServiceCard";
import { Section, SecTitle } from "../components/Layout";
import { ContactCard } from "../components/ContactCard";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { Icon, type IconName } from "../components/Icon";
import { BACKEND_PORTAL } from "../lib/api";
import { T } from "../lib/tokens";

type Variant = "primary" | "navy" | "secondary" | "ghost" | "danger" | "light";

interface Service {
  icon: IconName;
  title: string;
  desc: string;
  cta: string;
  accent: string;
  ctaVariant: Variant;
  onClick: () => void;
}

export function CwaHomePage() {
  const navigate = useNavigate();
  const services: Service[] = [
    {
      icon: "transit",
      title: "KSA Transit Visa Application",
      desc: "For Pakistani nationals requiring KSA transit or travel facilitation through the Embassy.",
      cta: "Open Service",
      accent: T.navy,
      ctaVariant: "navy",
      onClick: () => window.location.assign(`${BACKEND_PORTAL}/register`),
    },
    {
      icon: "user-add",
      title: "Pakistan Nurses Registration",
      desc: "For Grading Letters Issuance, resolution of Complaints and Settlement",
      cta: "Open Service",
      accent: T.green,
      ctaVariant: "primary",
      onClick: () => navigate("/nurses"),
    },
    {
      icon: "scale",
      title: "Legal Assistance & OPF Cards",
      desc: "Legal assistance, welfare support, labour complaints, and Overseas Pakistanis Foundation guidance.",
      cta: "Open Service",
      accent: "#2563eb",
      ctaVariant: "secondary",
      onClick: () => navigate("/legal-opf"),
    },
    {
      icon: "heart",
      title: "Death Cases Process",
      desc: "Death case documentation, repatriation coordination, and family support services.",
      cta: "Open Service",
      accent: "#6b21a8",
      ctaVariant: "secondary",
      onClick: () => navigate("/death-cases"),
    },
    {
      icon: "search",
      title: "Assistance in Locating / Contacting a Pakistani National",
      desc: "Request welfare assistance when a concerned person is unable to establish contact with a Pakistani national believed to be in Kuwait.",
      cta: "Open Service",
      accent: "#0f766e",
      ctaVariant: "secondary",
      onClick: () => navigate("/locating-assistance"),
    },
    {
      icon: "mail",
      title: "Community Feedback / Recommendations / Complaints",
      desc: "Submit community welfare feedback, recommendations, service-related complaints, or suggestions for improvement.",
      cta: "Open Service",
      accent: "#9333ea",
      ctaVariant: "secondary",
      onClick: () => navigate("/community-feedback"),
    },
  ];

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />

      {/* Hero */}
      <section
        style={{
          background: "linear-gradient(160deg,#2D4A6B 0%,#3A6080 100%)",
          padding: "64px 24px 60px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: -60,
            right: -60,
            width: 400,
            height: 400,
            borderRadius: "50%",
            background: "radial-gradient(circle,rgba(47,125,78,.12) 0%,transparent 70%)",
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
          <div style={{ flex: "1 1 340px", maxWidth: 560 }}>
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
              OFFICIAL PORTAL — COMMUNITY WELFARE WING
            </div>
            <h1
              style={{
                fontSize: "clamp(24px,3.6vw,44px)",
                fontWeight: 800,
                color: "#fff",
                lineHeight: 1.18,
                marginBottom: 14,
                maxWidth: 520,
              }}
            >
              Community Welfare Wing
              <br />
              <span style={{ color: "#9cf987" }}>Digital Services</span> Portal
            </h1>
            <p
              style={{
                fontSize: 14,
                color: "rgba(255,255,255,.7)",
                maxWidth: 460,
                lineHeight: 1.78,
                marginBottom: 28,
              }}
            >
              Online facilitation portal for selected Community Welfare services. Select the relevant
              service below to submit, track, or manage your request.
            </p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Btn
                variant="primary"
                size="lg"
                onClick={() =>
                  document.getElementById("cw-services")?.scrollIntoView({ behavior: "smooth" })
                }
              >
                Browse Services
              </Btn>
              <Btn
                size="lg"
                style={{
                  background: "rgba(255,255,255,.08)",
                  color: "#fff",
                  borderColor: "rgba(255,255,255,.2)",
                }}
                onClick={() => window.location.assign(`${BACKEND_PORTAL}/track-application`)}
              >
                <Icon name="search" size={17} color="white" /> Track Application
              </Btn>
            </div>
          </div>
          <div style={{ flex: "1 1 300px", maxWidth: 440 }}>
            <HeroCarousel inline caption="Serving the Pakistani Community in Kuwait" />
          </div>
        </div>
      </section>

      <main style={{ flex: 1 }}>
        <Section bg={T.bg} style={{ paddingTop: 64, paddingBottom: 64 }} id="cw-services">
          <SecTitle
            title="Community Welfare Services"
            sub="Select the relevant service to access forms, submit requests, or track existing applications."
            center
          />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(255px,1fr))",
              gap: 20,
            }}
          >
            {services.map((s) => (
              <ServiceCard
                key={s.title}
                icon={s.icon}
                title={s.title}
                desc={s.desc}
                cta={s.cta}
                accent={s.accent}
                ctaVariant={s.ctaVariant}
                onClick={s.onClick}
              />
            ))}
          </div>
        </Section>

        <Section bg={T.surfaceLow} style={{ paddingTop: 0 }}>
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
