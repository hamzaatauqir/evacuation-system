import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Card, Grid } from "../components/Layout";
import { Stepper } from "../components/Stepper";
import { FInput, FSelect, FTextarea } from "../components/FormField";
import { Btn } from "../components/Btn";
import { Icon } from "../components/Icon";
import { NoticeCard } from "../components/NoticeCard";
import { T } from "../lib/tokens";

const STEPS = ["Personal", "Contact", "Employment", "Welfare"];

interface FormState {
  fullName?: string;
  gender?: string;
  passport?: string;
  civilId?: string;
  nationality?: string;
  phone?: string;
  email?: string;
  address?: string;
  hospital?: string;
  jobTitle?: string;
  dept?: string;
  empType?: string;
  workPermit?: string;
  accommodation?: string;
  emergency?: string;
  remarks?: string;
  declared?: boolean;
}

export function NursesRegisterPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>({});
  const [done, setDone] = useState(false);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((p) => ({ ...p, [k]: v }));
  const inp = <K extends keyof FormState>(k: K) => ({
    value: (form[k] as string) || "",
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      set(k, e.target.value as FormState[K]),
  });

  if (done) {
    return (
      <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
        <PublicHeader />
        <div
          style={{
            minHeight: "70vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            flex: 1,
          }}
        >
          <div style={{ textAlign: "center", maxWidth: 480 }}>
            <div
              style={{
                width: 72,
                height: 72,
                borderRadius: "50%",
                background: T.successBg,
                border: "2px solid #86efac",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 20px",
              }}
            >
              <Icon name="check" size={32} color={T.successFg} />
            </div>
            <h2 style={{ fontSize: 24, fontWeight: 800, color: T.navy, marginBottom: 10 }}>
              Registration Submitted
            </h2>
            <p style={{ fontSize: 14, color: T.muted, lineHeight: 1.7, marginBottom: 24 }}>
              Your registration has been received by the Community Welfare Wing. A reference number
              will be sent to your provided contact details within 1–2 working days.
            </p>
            <NoticeCard type="info">
              Staff may contact you via WhatsApp for verification. No document upload was required at
              this stage.
            </NoticeCard>
            <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 24 }}>
              <Btn variant="primary" onClick={() => navigate("/nurses/login")}>
                Track Your Status
              </Btn>
              <Btn variant="light" onClick={() => navigate("/nurses")}>
                Back to Nurses Home
              </Btn>
            </div>
          </div>
        </div>
        <PageFooter />
      </div>
    );
  }

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <div style={{ background: "linear-gradient(160deg,#2D4A6B 0%,#3A6080 100%)", padding: "28px 24px 24px" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>
          <button
            onClick={() => navigate("/nurses")}
            style={{
              background: "none",
              border: "none",
              color: "rgba(255,255,255,.6)",
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
            <Icon name="exit" size={14} color="rgba(255,255,255,.6)" />
            Back to Nurses Home
          </button>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: "#fff", marginBottom: 4 }}>
            Nurse Community Registration
          </h1>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,.6)" }}>
            Community Welfare Wing — Official Registration Portal for Nurses in Kuwait
          </p>
        </div>
      </div>
      <div
        style={{
          height: 3,
          background: `linear-gradient(90deg,${T.green} ${((step + 1) / STEPS.length) * 100}%,${T.border} 0%)`,
        }}
      />

      <main style={{ flex: 1 }}>
        <div
          style={{
            maxWidth: 1000,
            margin: "0 auto",
            padding: "32px 24px",
            display: "flex",
            gap: 24,
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: "1 1 560px" }}>
            <Card>
              <Stepper steps={STEPS} current={step} />

              {step === 0 && (
                <div className="fade-in">
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, marginBottom: 20 }}>
                    Personal Information
                  </h3>
                  <Grid cols={2} gap={14}>
                    <div style={{ gridColumn: "1/-1" }}>
                      <FInput
                        label="Full Name as per Passport"
                        req
                        {...inp("fullName")}
                        placeholder="e.g. Fatima Malik"
                      />
                    </div>
                    <FSelect
                      label="Gender"
                      req
                      {...inp("gender")}
                      placeholder="Select gender"
                      options={["Female", "Male", "Other"]}
                    />
                    <FInput label="Passport Number" req {...inp("passport")} placeholder="e.g. AK1234567" />
                    <FInput label="Civil ID Number" req {...inp("civilId")} placeholder="e.g. 285-123-456-7" />
                    <FSelect
                      label="Nationality"
                      req
                      {...inp("nationality")}
                      placeholder="Select"
                      options={["Pakistani", "Other"]}
                    />
                  </Grid>
                </div>
              )}

              {step === 1 && (
                <div className="fade-in">
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, marginBottom: 20 }}>
                    Contact Details
                  </h3>
                  <FInput
                    label="Phone / WhatsApp Number"
                    req
                    {...inp("phone")}
                    type="tel"
                    placeholder="+965 XXXX XXXX"
                  />
                  <FInput label="Email Address" {...inp("email")} type="email" placeholder="your@email.com" />
                  <FTextarea
                    label="Current Residential Address in Kuwait"
                    req
                    {...inp("address")}
                    placeholder="Block, Street, Area, Governorate"
                    rows={3}
                  />
                </div>
              )}

              {step === 2 && (
                <div className="fade-in">
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, marginBottom: 20 }}>
                    Employment Details
                  </h3>
                  <FInput
                    label="Hospital / Workplace Name"
                    req
                    {...inp("hospital")}
                    placeholder="e.g. Al Sabah Hospital"
                  />
                  <FInput
                    label="Job Title / Designation"
                    req
                    {...inp("jobTitle")}
                    placeholder="e.g. Staff Nurse"
                  />
                  <Grid cols={2} gap={14}>
                    <FInput label="Department" {...inp("dept")} placeholder="e.g. Cardiology" />
                    <FSelect
                      label="Employer Type"
                      {...inp("empType")}
                      placeholder="Select"
                      options={["Ministry of Health (MOH)", "Private Hospital", "Clinic", "Other"]}
                    />
                  </Grid>
                  <FInput
                    label="Work Permit / IQAMA Number"
                    {...inp("workPermit")}
                    placeholder="If available"
                  />
                </div>
              )}

              {step === 3 && (
                <div className="fade-in">
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, marginBottom: 20 }}>
                    Welfare & Accommodation
                  </h3>
                  <FSelect
                    label="Current Accommodation Status"
                    req
                    {...inp("accommodation")}
                    placeholder="Select"
                    options={[
                      "MOH Provided",
                      "Hospital Provided",
                      "Private (Self-Arranged)",
                      "Embassy Shelter",
                      "Other",
                    ]}
                  />
                  <FInput
                    label="Emergency Contact Number"
                    req
                    {...inp("emergency")}
                    type="tel"
                    placeholder="+965 or Pakistan number"
                  />
                  <FTextarea
                    label="Remarks / Special Concerns"
                    {...inp("remarks")}
                    placeholder="Any welfare concerns, special circumstances, or information for the Embassy..."
                    rows={3}
                  />
                  <div
                    style={{
                      marginTop: 20,
                      padding: "14px 16px",
                      background: T.surfaceLow,
                      borderRadius: 10,
                      border: `1px solid ${T.borderLt}`,
                    }}
                  >
                    <label
                      style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }}
                    >
                      <input
                        type="checkbox"
                        style={{ marginTop: 3, accentColor: T.navy, width: 16, height: 16, flexShrink: 0 }}
                        checked={!!form.declared}
                        onChange={(e) => set("declared", e.target.checked)}
                      />
                      <span style={{ fontSize: 13, color: T.text, lineHeight: 1.6 }}>
                        I declare that the information provided is accurate and complete. I understand
                        it will be used for official community welfare records by the Embassy of
                        Pakistan, Kuwait.
                      </span>
                    </label>
                  </div>
                </div>
              )}

              {/* Navigation buttons */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: 28,
                  paddingTop: 20,
                  borderTop: `1px solid ${T.borderLt}`,
                }}
              >
                <Btn
                  variant="light"
                  onClick={() => (step === 0 ? navigate("/nurses") : setStep((s) => s - 1))}
                >
                  {step === 0 ? "Cancel" : "← Back"}
                </Btn>
                <div style={{ display: "flex", gap: 10 }}>
                  {step < 3 ? (
                    <Btn variant="navy" onClick={() => setStep((s) => s + 1)}>
                      Continue →
                    </Btn>
                  ) : (
                    <Btn variant="primary" disabled={!form.declared} onClick={() => setDone(true)}>
                      Submit Registration
                    </Btn>
                  )}
                </div>
              </div>
            </Card>
          </div>

          {/* Sidebar */}
          <div style={{ width: 280, flexShrink: 0 }}>
            <Card style={{ borderTop: `3px solid ${T.green}`, marginBottom: 14 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: T.navy,
                  marginBottom: 12,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <Icon name="info" size={15} color={T.green} />
                Important Notice
              </div>
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {[
                  "Enter accurate details as per your official documents.",
                  "Information is used for community welfare and official Embassy records.",
                  "Staff may contact you via WhatsApp for verification.",
                  "No document upload is required here.",
                  "Supporting documents may be requested via official email after initial verification.",
                ].map((t, i) => (
                  <li
                    key={i}
                    style={{
                      display: "flex",
                      gap: 8,
                      fontSize: 12,
                      color: T.muted,
                      lineHeight: 1.6,
                      marginBottom: 8,
                    }}
                  >
                    <div
                      style={{
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        background: T.green,
                        flexShrink: 0,
                        marginTop: 6,
                      }}
                    />
                    {t}
                  </li>
                ))}
              </ul>
            </Card>
            <Card style={{ borderTop: `3px solid ${T.navy}` }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.navy, marginBottom: 10 }}>
                Helpline
              </div>
              <a
                href="mailto:parepkuwaitcwa37@gmail.com"
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  fontSize: 12,
                  color: T.infoFg,
                  marginBottom: 8,
                }}
              >
                <Icon name="mail" size={14} color={T.infoFg} />
                parepkuwaitcwa37@gmail.com
              </a>
              <a
                href="tel:+96555977292"
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  fontSize: 12,
                  color: T.infoFg,
                }}
              >
                <Icon name="phone" size={14} color={T.infoFg} />
                +965 5597 7292
              </a>
              <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${T.borderLt}` }}>
                <button
                  onClick={() => navigate("/nurses/login")}
                  style={{
                    background: "none",
                    border: "none",
                    fontSize: 12,
                    color: T.muted,
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  Already registered? Login / Track →
                </button>
              </div>
            </Card>
          </div>
        </div>
      </main>
      <PageFooter />
    </div>
  );
}
