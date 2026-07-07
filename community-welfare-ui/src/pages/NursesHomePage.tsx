import { useNavigate } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { HeroCarousel } from "../components/HeroCarousel";
import { NoticeCard } from "../components/NoticeCard";
import { ServiceCard } from "../components/ServiceCard";
import { Section, SecTitle } from "../components/Layout";
import { ProcessSteps } from "../components/ProcessSteps";
import { ContactCard } from "../components/ContactCard";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { T } from "../lib/tokens";

export function NursesHomePage() {
  const navigate = useNavigate();
  const steps = [
    { title: "Register / Login", desc: "Create or access your account with your email and passport (Civil ID when available)." },
    { title: "Submit Request", desc: "Use services from inside your nurse portal." },
    { title: "Embassy Review", desc: "Community Welfare Wing officers verify your information." },
    { title: "Track Status", desc: "Receive updates in your nurse portal dashboard." },
  ];

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />

      <section style={{ background: "linear-gradient(160deg,#2D4A6B 0%,#3A6080 100%)", padding: "72px 24px 64px", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(ellipse at 70% 40%,rgba(47,125,78,.15) 0%,transparent 55%)", pointerEvents: "none" }} />
        <div style={{ maxWidth: 1200, margin: "0 auto", position: "relative", zIndex: 1, display: "flex", alignItems: "center", gap: 48, flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 340px", maxWidth: 540 }}>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(255,255,255,.1)", border: "1px solid rgba(255,255,255,.18)", borderRadius: 20, padding: "5px 14px", fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,.88)", marginBottom: 22, letterSpacing: ".05em" }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#6ee79a" }} />
              HEALTH WORKERS PORTAL
            </div>
            <h1 style={{ fontSize: "clamp(24px,3.5vw,44px)", fontWeight: 800, color: "#fff", lineHeight: 1.2, marginBottom: 14 }}>
              Pakistan Nurses / Health Workers
              <br />
              <span style={{ color: "#9cf987" }}>Registration Portal</span>
            </h1>
            <p style={{ fontSize: 14, color: "rgba(255,255,255,.68)", maxWidth: 460, lineHeight: 1.75, marginBottom: 22 }}>
              A dedicated portal for the Pakistani nursing and health worker community in Kuwait has been
              established for registration, welfare assistance, facility follow-up, and communication with
              the Community Welfare Wing.
            </p>
            <NoticeCard type="info">
              <strong>Important:</strong> After you register and verify your login, requests, welfare matters, and
              Embassy messages are handled inside the secure nurse portal only.
            </NoticeCard>
          </div>
          <div style={{ flex: "1 1 300px", maxWidth: 420 }}>
            <HeroCarousel inline caption="Embassy of Pakistan, Kuwait — Community Welfare Wing" />
          </div>
        </div>
      </section>

      <main style={{ flex: 1 }}>
        <Section bg={T.bg}>
          <SecTitle title="Nurses / Health Workers Public Access" sub="Start from registration or login/track to continue into your health workers portal." center />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(255px,1fr))', gap: 18 }}>
            <ServiceCard icon="user-add" title="Nurses / Health Workers Registration" desc="Registration for Pakistani nursing and health worker community members in Kuwait." cta="Register Now" ctaVariant="primary" accent={T.green} onClick={() => navigate('/nurses/register')} />
            <ServiceCard icon="user" title="Existing Health Worker Login / Track Registration" desc="Login and open your portal dashboard for welfare assistance, facility follow-up, and tracking." cta="Open Portal" ctaVariant="navy" accent={T.navy} onClick={() => navigate('/nurses/login')} />
          </div>
        </Section>

        <Section bg={T.surfaceLow}>
          <SecTitle
            title="Services available inside Health Workers Portal"
            sub="After registration/login, nurses and health workers can submit requests, confirm stay arrangements, view Embassy messages, and track updates from one secure portal."
            center
          />
          <div style={{ maxWidth: 640, margin: "0 auto", textAlign: "center" }}>
            <div style={{ display: "flex", justifyContent: "center", marginTop: 8 }}>
              <Btn variant="navy" onClick={() => navigate("/nurses/login")}>
                Open Nurse Portal
              </Btn>
            </div>
          </div>
        </Section>

        <Section bg={T.surfaceLow}>
          <SecTitle title="Service Delivery Process" center />
          <ProcessSteps steps={steps} />
        </Section>

        <Section bg={T.bg} style={{ paddingTop: 0 }}>
          <ContactCard email="parepkuwaitcwa37@gmail.com" phone="+965 5597 7292" hours="Sunday – Thursday, 8:00 AM – 3:30 PM (Kuwait Time)" />
        </Section>
      </main>

      <PageFooter />
    </div>
  );
}
