import { Link, useNavigate } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { HeroCarousel } from "../components/HeroCarousel";
import { NoticeCard } from "../components/NoticeCard";
import { ServiceCard } from "../components/ServiceCard";
import { Section, SecTitle, Card } from "../components/Layout";
import { ProcessSteps } from "../components/ProcessSteps";
import { ContactCard } from "../components/ContactCard";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { Icon } from "../components/Icon";
import { T } from "../lib/tokens";

export function NursesHomePage() {
  const navigate = useNavigate();
  const steps = [
    { title: "Register / Login", desc: "Create or access your account using your Civil ID and Passport." },
    { title: "Submit Request", desc: "Use services from inside your nurse portal." },
    { title: "Embassy Review", desc: "Community Welfare Wing officers verify your information." },
    { title: "Track Status", desc: "Receive updates in your nurse portal dashboard." },
  ];

  const locked = [
    { key: 'accommodation', title: 'Accommodation Request', to: '/nurses/login?next=accommodation' },
    { key: 'complaint', title: 'Complaint / Welfare Issue', to: '/nurses/login?next=complaint' },
    { key: 'leaving-notice', title: 'Leaving Notice / Exit', to: '/nurses/login?next=leaving-notice' },
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
              NURSES PORTAL
            </div>
            <h1 style={{ fontSize: "clamp(24px,3.5vw,44px)", fontWeight: 800, color: "#fff", lineHeight: 1.2, marginBottom: 14 }}>
              Pakistan Nurses
              <br />
              <span style={{ color: "#9cf987" }}>Registration Portal</span>
            </h1>
            <p style={{ fontSize: 14, color: "rgba(255,255,255,.68)", maxWidth: 460, lineHeight: 1.75, marginBottom: 22 }}>
              Register first, then login/track your registration to access accommodation requests,
              welfare complaints, and leaving notices inside your personal nurse dashboard.
            </p>
            <NoticeCard type="info">
              <strong>Important:</strong> Accommodation requests, welfare complaints, and leaving notices are
              available inside the nurse portal after registration/login.
            </NoticeCard>
          </div>
          <div style={{ flex: "1 1 300px", maxWidth: 420 }}>
            <HeroCarousel inline caption="Embassy of Pakistan, Kuwait — Community Welfare Wing" />
          </div>
        </div>
      </section>

      <main style={{ flex: 1 }}>
        <Section bg={T.bg}>
          <SecTitle title="Nurses Public Access" sub="Start from registration or login/track to continue into your nurse portal." center />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(255px,1fr))', gap: 18 }}>
            <ServiceCard icon="user-add" title="New Nurses Registration" desc="Initial registration for newly arrived Pakistani nursing staff in Kuwait." cta="Register Now" ctaVariant="primary" accent={T.green} onClick={() => navigate('/nurses/register')} />
            <ServiceCard icon="user" title="Existing Nurse Login / Track Registration" desc="Login and open your nurse portal dashboard for requests and tracking." cta="Login / Track" ctaVariant="navy" accent={T.navy} onClick={() => navigate('/nurses/login')} />
          </div>
        </Section>

        <Section bg={T.surfaceLow}>
          <SecTitle title="Services Available Inside Nurse Portal" sub="These services require registration/login verification." center />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 14 }}>
            {locked.map((s) => (
              <Card key={s.key} style={{ borderTop: '3px solid #94a3b8' }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
                  <Icon name="info" size={16} color="#64748b" />
                  <strong style={{ color: '#334155' }}>{s.title}</strong>
                </div>
                <p style={{ color: '#64748b', fontSize: 13, marginBottom: 12 }}>
                  Available after login/track verification inside nurse portal.
                </p>
                <Link to={s.to}><Btn variant="light">Login to Access</Btn></Link>
              </Card>
            ))}
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
