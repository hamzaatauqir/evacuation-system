import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Section, SecTitle, Card, Grid } from "../components/Layout";
import { Icon } from "../components/Icon";
import { Btn } from "../components/Btn";
import { ProcessSteps } from "../components/ProcessSteps";
import { NoticeCard } from "../components/NoticeCard";
import { FInput, FSelect, FTextarea } from "../components/FormField";
import { SuccessState } from "../components/FormPage";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

interface FormState {
  decName?: string;
  decPassport?: string;
  decCivil?: string;
  decNat?: string;
  authority?: string;
  contactName?: string;
  relation?: string;
  contactPhone?: string;
  contactEmail?: string;
  desc?: string;
}

const STEPS = [
  { title: "Notify Embassy", desc: "Contact the Community Welfare Wing by phone or submit details below." },
  { title: "Submit Details", desc: "Provide case details, authority contacts, and family information." },
  { title: "Documentation", desc: "Embassy reviews and assists with official documentation." },
  { title: "Coordination", desc: "Coordination with authorities, family, and repatriation support." },
];

export function DeathCasesPage() {
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
      await api.post("/api/death-cases/intake", {
        deceased_name: (form.decName || "").trim(),
        deceased_passport: (form.decPassport || "").trim(),
        deceased_cnic: (form.decCivil || "").trim(),
        date_of_death: "",
        reporter_name: (form.contactName || "").trim(),
        reporter_mobile: (form.contactPhone || "").trim(),
        reporter_email: (form.contactEmail || "").trim(),
        reporter_relation: (form.relation || "").trim(),
        hospital_or_authority: (form.authority || "").trim(),
        description: (form.desc || "").trim(),
        priority: "Urgent",
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
              color: "rgba(255,255,255,.75)",
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
            <Icon name="exit" size={14} color="rgba(255,255,255,.75)" />
            Back to Home
          </button>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: "#fff", marginBottom: 8 }}>
            Death Cases Process
          </h1>
          <p style={{ fontSize: 14, color: "rgba(255,255,255,.6)", maxWidth: 520, lineHeight: 1.7 }}>
            Guidance for documentation, repatriation coordination, and family support. The Embassy is
            here to assist you during this difficult time.
          </p>
        </div>
      </section>
      <div style={{ height: 3, background: "linear-gradient(90deg,#6b21a8,#7c3aed)" }} />

      <main style={{ flex: 1 }}>
        <Section bg={T.surfaceLow}>
          <SecTitle title="Process Overview" center />
          <ProcessSteps steps={STEPS} />
        </Section>

        <Section bg={T.bg}>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 520px" }}>
              <div style={{ marginBottom: 16 }}>
                <NoticeCard type="warning" title="Urgent Cases">
                  For immediate assistance, call +965 5597 7292. Do not wait to fill this form.
                </NoticeCard>
              </div>
              <Card>
                {submitted ? (
                  <SuccessState message="Your request has been received. If you provided an email address, please check your inbox and verify your email address to receive future updates. Email verification pending." />
                ) : (
                  <>
                    <h3 style={{ fontSize: 15, fontWeight: 700, color: T.navy, marginBottom: 16 }}>
                      Deceased Person Details
                    </h3>
                    <Grid cols={2} gap={14}>
                      <FInput
                        label="Full Name of Deceased"
                        req
                        {...inp("decName")}
                        placeholder="As per passport"
                      />
                      <FInput
                        label="Passport Number"
                        req
                        {...inp("decPassport")}
                        placeholder="Passport number"
                      />
                      <FInput
                        label="Civil ID (if available)"
                        {...inp("decCivil")}
                        placeholder="Civil ID number"
                      />
                      <FInput label="Nationality" {...inp("decNat")} placeholder="e.g. Pakistani" />
                    </Grid>
                    <FTextarea
                      label="Hospital / Authority / Police Station Involved"
                      req
                      {...inp("authority")}
                      placeholder="Name and contact of hospital, mortuary, or police station..."
                      rows={2}
                    />
                    <div style={{ height: 1, background: T.borderLt, margin: "18px 0" }} />
                    <h3 style={{ fontSize: 15, fontWeight: 700, color: T.navy, marginBottom: 16 }}>
                      Contact Person (Family / Representative)
                    </h3>
                    <Grid cols={2} gap={14}>
                      <FInput
                        label="Contact Person Name"
                        req
                        {...inp("contactName")}
                        placeholder="Family member or representative"
                      />
                      <FSelect
                        label="Relationship to Deceased"
                        req
                        {...inp("relation")}
                        placeholder="Select"
                        options={["Spouse", "Parent", "Sibling", "Child", "Employer", "Friend", "Other"]}
                      />
                      <FInput
                        label="Phone Number"
                        req
                        {...inp("contactPhone")}
                        type="tel"
                        placeholder="+965 or Pakistan number"
                      />
                      <FInput
                        label="Email (optional)"
                        {...inp("contactEmail")}
                        type="email"
                        placeholder="For correspondence"
                      />
                    </Grid>
                    <FTextarea
                      label="Description / Assistance Required"
                      req
                      {...inp("desc")}
                      placeholder="Provide details of the situation and what assistance is required..."
                      rows={4}
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
                        {submitting ? "Submitting…" : "Submit Case Details"}
                      </Btn>
                    </div>
                  </>
                )}
              </Card>
            </div>
            <div style={{ width: 260, flexShrink: 0 }}>
              <Card style={{ borderTop: "3px solid #6b21a8", marginBottom: 14 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 8 }}>
                  Emergency Contact
                </div>
                <p style={{ fontSize: 12, color: T.muted, lineHeight: 1.65, marginBottom: 12 }}>
                  For urgent cases, please contact the Embassy directly rather than waiting for form
                  review.
                </p>
                <a
                  href="tel:+96555977292"
                  style={{
                    display: "flex",
                    gap: 7,
                    alignItems: "center",
                    fontSize: 13,
                    fontWeight: 700,
                    color: T.navy,
                    marginBottom: 8,
                  }}
                >
                  <Icon name="phone" size={15} color={T.green} />
                  +965 5597 7292
                </a>
                <a
                  href="mailto:parepkuwaitcwa37@gmail.com"
                  style={{
                    display: "flex",
                    gap: 7,
                    alignItems: "center",
                    fontSize: 12,
                    color: T.infoFg,
                  }}
                >
                  <Icon name="mail" size={13} color={T.infoFg} />
                  parepkuwaitcwa37@gmail.com
                </a>
              </Card>
            </div>
          </div>
        </Section>
      </main>
      <PageFooter />
    </div>
  );
}
