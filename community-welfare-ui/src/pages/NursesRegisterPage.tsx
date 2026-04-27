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
import { api } from "../lib/api";

const STEPS = ["Personal", "Contact", "Employment", "Welfare", "Account"];

interface FormState {
  fullName?: string;
  gender?: string;
  passport?: string;
  civilId?: string;
  cnic?: string;
  nationality?: string;
  phone?: string;
  email?: string;
  address?: string;
  hospital?: string;
  jobTitle?: string;
  dept?: string;
  empType?: string;
  workPermit?: string;
  arrivalDate?: string;
  batchNumber?: string;
  accommodation?: string;
  emergency?: string;
  remarks?: string;
  declared?: boolean;
  password?: string;
  confirmPassword?: string;
}

function passwordOk(pw: string): string | null {
  if (!pw || pw.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Za-z]/.test(pw)) return "Password must contain at least one letter.";
  if (!/\d/.test(pw)) return "Password must contain at least one number.";
  return null;
}

export function NursesRegisterPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>({});
  const [done, setDone] = useState(false);
  const [submittedRef, setSubmittedRef] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPw, setShowPw] = useState(false);

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
            <p style={{ fontSize: 14, color: T.muted, lineHeight: 1.7, marginBottom: 12 }}>
              Registration submitted successfully. Please log in to access your Nurse Portal.
            </p>
            {submittedRef ? (
              <p style={{ fontSize: 14, color: T.navy, fontWeight: 700, marginBottom: 24 }}>
                Your reference: {submittedRef}
              </p>
            ) : null}
            <NoticeCard type="info">
              Staff may contact you via WhatsApp for verification. No document upload was required at
              this stage.
            </NoticeCard>
            <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 24 }}>
              <Btn variant="primary" onClick={() => navigate("/nurses/login")}>
                Log in to Nurse Portal
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
                    <FInput label="CNIC (Pakistan National ID)" req {...inp("cnic")} placeholder="13-digit CNIC" />
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
                  <FInput label="Email Address (required for your account)" req {...inp("email")} type="email" placeholder="your@email.com" />
                  <FTextarea
                    label="Current address in Kuwait"
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
                  <Grid cols={2} gap={14} style={{ marginTop: 8 }}>
                    <FInput label="Date arrived in Kuwait" req {...inp("arrivalDate")} type="date" />
                    <FInput label="Batch / cohort reference" req {...inp("batchNumber")} placeholder="As issued by authorities" />
                  </Grid>
                </div>
              )}

              {step === 3 && (
                <div className="fade-in">
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, marginBottom: 20 }}>
                    Welfare & current arrangement
                  </h3>
                  <FSelect
                    label="Current arrangement (MOH / hospital / private / other)"
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

              {step === 4 && (
                <div className="fade-in">
                  <h3 style={{ fontSize: 16, fontWeight: 700, color: T.navy, marginBottom: 20 }}>
                    Account password
                  </h3>
                  <p style={{ fontSize: 13, color: T.muted, marginBottom: 16, lineHeight: 1.6 }}>
                    Create a password for your Nurse Portal (minimum 8 characters, at least one letter and one
                    number). You will use this with your email or passport or Civil ID to sign in.
                  </p>
                  <label style={{ display: "block", marginBottom: 12, fontSize: 13 }}>
                    Password
                    <div style={{ display: "flex", gap: 8 }}>
                      <input
                        className="f-input"
                        style={{ flex: 1 }}
                        type={showPw ? "text" : "password"}
                        value={form.password || ""}
                        onChange={(e) => set("password", e.target.value)}
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="f-input"
                        style={{ width: "auto", cursor: "pointer", padding: "8px 12px" }}
                        onClick={() => setShowPw((s) => !s)}
                      >
                        {showPw ? "Hide" : "Show"}
                      </button>
                    </div>
                  </label>
                  <label style={{ display: "block", marginBottom: 12, fontSize: 13 }}>
                    Confirm password
                    <input
                      className="f-input"
                      type={showPw ? "text" : "password"}
                      value={form.confirmPassword || ""}
                      onChange={(e) => set("confirmPassword", e.target.value)}
                      autoComplete="new-password"
                    />
                  </label>
                </div>
              )}

              {/* Navigation buttons */}
              {submitError ? (
                <div style={{ marginTop: 16 }}>
                  <NoticeCard type="warning">{submitError}</NoticeCard>
                </div>
              ) : null}
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
                  {step < 4 ? (
                    <Btn variant="navy" onClick={() => setStep((s) => s + 1)}>
                      Continue →
                    </Btn>
                  ) : (
                    <Btn
                      variant="primary"
                      disabled={!form.declared || submitting}
                      onClick={async () => {
                        setSubmitError("");
                        const pwErr = passwordOk(form.password || "");
                        if (pwErr) {
                          setSubmitError(pwErr);
                          return;
                        }
                        if ((form.password || "") !== (form.confirmPassword || "")) {
                          setSubmitError("Password and confirmation do not match.");
                          return;
                        }
                        const applyAcc = /shelter|embassy/i.test(form.accommodation || "") ? "Yes" : "No";
                        setSubmitting(true);
                        try {
                          const res = await api.post<{
                            success?: boolean;
                            ok?: boolean;
                            reference?: string;
                            reference_id?: string;
                            error?: string;
                          }>("/api/nurses/register", {
                            full_name: form.fullName,
                            passport_number: form.passport,
                            civil_id: form.civilId,
                            cnic: form.cnic,
                            mobile: form.phone,
                            email: form.email,
                            arrival_date: form.arrivalDate,
                            batch_number: form.batchNumber,
                            hospital: form.hospital,
                            designation: form.jobTitle,
                            degree_type: form.dept || "",
                            remarks: form.remarks || "",
                            current_accommodation: form.accommodation || "",
                            applying_for_accommodation: applyAcc,
                            issue_notice: "",
                            password: form.password,
                            confirm_password: form.confirmPassword,
                          });
                          if (!res.success && !res.ok) {
                            setSubmitError(res.error || "Registration failed.");
                            return;
                          }
                          setSubmittedRef((res.reference || res.reference_id || "").toString());
                          setDone(true);
                        } catch (e) {
                          setSubmitError((e as Error).message || "Registration failed.");
                        } finally {
                          setSubmitting(false);
                        }
                      }}
                    >
                      {submitting ? "Submitting…" : "Submit registration"}
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
                  Already registered? Sign in →
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
