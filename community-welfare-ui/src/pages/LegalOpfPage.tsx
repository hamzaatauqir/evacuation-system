import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Section, Card, Grid } from "../components/Layout";
import { Icon, type IconName } from "../components/Icon";
import { Btn } from "../components/Btn";
import { FInput, FSelect, FTextarea } from "../components/FormField";
import { SuccessState } from "../components/FormPage";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

interface FormState {
  name?: string;
  id?: string;
  phone?: string;
  email?: string;
  sponsor?: string;
  desc?: string;
  urgency?: string;
  serviceType?: string;
}

interface ServiceTile {
  k: string;
  icon: IconName;
  t: string;
  d: string;
}

const SERVICES: ServiceTile[] = [
  { k: "legal-assist", icon: "scale", t: "Legal Assistance", d: "Labour disputes, contract violations, Embassy legal referral." },
  { k: "labour", icon: "building", t: "Labour Complaint", d: "File a complaint against employer or sponsor." },
  { k: "opf", icon: "tag", t: "OPF Card Guidance", d: "Overseas Pakistanis Foundation card application support." },
  { k: "welfare", icon: "heart", t: "General Welfare Support", d: "Financial hardship, emergency repatriation, shelter support." },
];

export function LegalOpfPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>({});
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const inp = <K extends keyof FormState>(k: K) => ({
    value: (form[k] as string) || "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm((p) => ({ ...p, [k]: e.target.value as FormState[K] })),
  });

  async function submit() {
    setError("");
    setSubmitting(true);
    try {
      await api.post("/api/legal-cases/intake", {
        full_name: (form.name || "").trim(),
        passport_number: (form.id || "").trim(),
        cnic: "",
        civil_id: "",
        mobile: (form.phone || "").trim(),
        email: (form.email || "").trim(),
        current_address: "",
        case_type: (form.serviceType || "Legal Assistance").trim(),
        subject: (form.serviceType || "Legal Assistance").trim(),
        description: (form.desc || "").trim(),
        priority: (form.urgency || "Normal").trim() === "Emergency" ? "Urgent" : (form.urgency || "Normal").trim(),
        consent: true,
      });
      setSubmitted(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <section
        style={{
          background: "linear-gradient(160deg,#2D4A6B 0%,#3A6080 100%)",
          padding: "48px 24px 40px",
        }}
      >
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <button
            onClick={() => navigate("/")}
            style={{
              background: "none",
              border: "none",
              color: "rgba(255,255,255,.7)",
              fontSize: 12,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              marginBottom: 12,
              padding: 0,
              fontWeight: 600,
            }}
          >
            <Icon name="exit" size={14} color="rgba(255,255,255,.7)" />
            Back to Home
          </button>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: "#fff", marginBottom: 8 }}>
            Legal Assistance & OPF Cards
          </h1>
          <p style={{ fontSize: 14, color: "rgba(255,255,255,.65)", maxWidth: 540 }}>
            Legal assistance, welfare support, labour complaints, and Overseas Pakistanis Foundation
            guidance for Pakistani nationals in Kuwait.
          </p>
        </div>
      </section>
      <div style={{ height: 3, background: "linear-gradient(90deg,#2563eb,#1d4ed8)" }} />

      <main style={{ flex: 1 }}>
        <Section bg={T.bg}>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 520px" }}>
              <div style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.navy, marginBottom: 12 }}>
                  Select Service Type
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill,minmax(210px,1fr))",
                    gap: 12,
                  }}
                >
                  {SERVICES.map((s) => {
                    const active = form.serviceType === s.k;
                    return (
                      <button
                        key={s.k}
                        onClick={() => setForm((p) => ({ ...p, serviceType: s.k }))}
                        style={{
                          padding: 14,
                          borderRadius: 10,
                          border: `1.5px solid ${active ? "#2563eb" : T.borderLt}`,
                          background: active ? "#eff6ff" : T.surface,
                          cursor: "pointer",
                          textAlign: "left",
                          transition: "all .15s",
                        }}
                      >
                        <div
                          style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 5 }}
                        >
                          <Icon name={s.icon} size={17} color={active ? "#2563eb" : T.muted} />
                          <span
                            style={{
                              fontSize: 13,
                              fontWeight: 700,
                              color: active ? "#1e40af" : T.navy,
                            }}
                          >
                            {s.t}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: T.mutedLt, lineHeight: 1.5 }}>
                          {s.d}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
              <Card>
                {submitted ? (
                  <SuccessState message="Your request has been received. If you provided an email address, please check your inbox and verify your email address to receive future updates. Email verification pending." />
                ) : (
                  <>
                    <Grid cols={2} gap={14}>
                      <FInput label="Full Name" req {...inp("name")} placeholder="As per passport" />
                      <FInput
                        label="Passport / Civil ID"
                        req
                        {...inp("id")}
                        placeholder="Document number"
                      />
                      <FInput
                        label="Contact Number"
                        req
                        {...inp("phone")}
                        type="tel"
                        placeholder="+965 XXXX XXXX"
                      />
                      <FInput label="Email" {...inp("email")} type="email" placeholder="optional" />
                    </Grid>
                    <FInput
                      label="Employer / Sponsor Name"
                      {...inp("sponsor")}
                      placeholder="If relevant to your case"
                    />
                    <FTextarea
                      label="Description of Your Case"
                      req
                      {...inp("desc")}
                      placeholder="Provide full details of your situation, the issue, and what assistance you require..."
                      rows={4}
                    />
                    <FSelect
                      label="Urgency"
                      req
                      {...inp("urgency")}
                      placeholder="Select"
                      options={["Normal", "Urgent", "Emergency"]}
                    />
                    {error && <p style={{ color: T.error, fontSize: 12 }}>{error}</p>}
                    <div
                      style={{
                        marginTop: 22,
                        display: "flex",
                        justifyContent: "flex-end",
                        gap: 10,
                        paddingTop: 18,
                        borderTop: `1px solid ${T.borderLt}`,
                      }}
                    >
                      <Btn variant="light" onClick={() => navigate("/")}>
                        Cancel
                      </Btn>
                      <Btn variant="navy" icon="check" onClick={submit} disabled={submitting}>
                        {submitting ? "Submitting…" : "Submit Request"}
                      </Btn>
                    </div>
                  </>
                )}
              </Card>
            </div>
            <div style={{ width: 260, flexShrink: 0 }}>
              <Card style={{ borderTop: "3px solid #2563eb", marginBottom: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 10 }}>
                  Working Hours
                </div>
                <div style={{ fontSize: 12, color: T.muted, lineHeight: 1.7 }}>
                  Sunday – Thursday
                  <br />
                  8:00 AM – 3:30 PM
                  <br />
                  Kuwait Time
                </div>
                <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${T.borderLt}` }}>
                  <a
                    href="mailto:parepkuwaitcwa37@gmail.com"
                    style={{
                      display: "flex",
                      gap: 7,
                      alignItems: "center",
                      fontSize: 12,
                      color: T.infoFg,
                      marginBottom: 6,
                    }}
                  >
                    <Icon name="mail" size={13} color={T.infoFg} />
                    parepkuwaitcwa37@gmail.com
                  </a>
                  <a
                    href="tel:+96555977292"
                    style={{
                      display: "flex",
                      gap: 7,
                      alignItems: "center",
                      fontSize: 12,
                      color: T.infoFg,
                    }}
                  >
                    <Icon name="phone" size={13} color={T.infoFg} />
                    +965 5597 7292
                  </a>
                </div>
              </Card>
            </div>
          </div>
        </Section>
      </main>
      <PageFooter />
    </div>
  );
}
