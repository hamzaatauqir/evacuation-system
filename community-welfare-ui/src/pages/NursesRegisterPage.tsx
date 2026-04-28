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
const PROFESSIONAL_CATEGORIES = ["Nurse", "Other Health Worker", "Doctor"];
const VENDOR_ELIGIBLE_CATEGORIES = ["Nurse", "Other Health Worker"];
const CURRENT_ARRANGEMENTS = [
  "MOH Arranged",
  { value: "Embassy Contracted / Arranged", label: "AJA Care Vendor Embassy Contracted" },
  "Private (Self Arranged)",
  "Other",
];
const APPROVED_VENDOR_OPTIONS = ["AJA Care", "Other / Not Sure"];
const QUALIFICATION_OPTIONS_BY_CATEGORY: Record<string, string[]> = {
  Nurse: ["Diploma Nurse", "BSN Nursing", "Other"],
  Doctor: ["Doctor MBBS", "Doctor BDS", "Other"],
  "Other Health Worker": ["Diploma Nurse", "BSN Nursing", "Doctor MBBS", "Doctor BDS", "Other"],
};

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
  professionalCategory?: string;
  qualificationDegree?: string;
  qualificationDegreeOther?: string;
  dept?: string;
  empType?: string;
  workPermit?: string;
  arrivalDate?: string;
  batchNumber?: string;
  currentArrangement?: string;
  vendorName?: string;
  facilityName?: string;
  facilityArea?: string;
  dateShiftedToFacility?: string;
  contractStartDate?: string;
  stayRemindersOptIn?: string;
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
  const isVendorEligible = VENDOR_ELIGIBLE_CATEGORIES.includes(form.professionalCategory || "");
  const isEmbassyArranged = form.currentArrangement === "Embassy Contracted / Arranged";
  const showAreaField =
    isVendorEligible &&
    ["Embassy Contracted / Arranged", "Private (Self Arranged)", "MOH Arranged"].includes(form.currentArrangement || "");
  const showStayArrangementWorkflow = isVendorEligible;
  const showVendorSelection = isVendorEligible && isEmbassyArranged;
  const qualificationOptions = QUALIFICATION_OPTIONS_BY_CATEGORY[form.professionalCategory || ""] || [];
  const showQualificationOther = form.qualificationDegree === "Other";

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
            Nurses / Health Workers Registration
          </h1>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,.6)" }}>
            Community Welfare Wing — Official Registration Portal for Pakistani nurses and health workers in Kuwait
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
                    <FInput
                      label="Civil ID Number (optional)"
                      hint="Leave blank if not yet issued."
                      {...inp("civilId")}
                      placeholder="e.g. 285-123-456-7"
                    />
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
                  <FSelect
                    label="Professional Category"
                    req
                    value={form.professionalCategory || ""}
                    onChange={(e) => {
                      const professionalCategory = e.target.value;
                      setForm((prev) => ({
                        ...prev,
                        professionalCategory,
                        qualificationDegree: "",
                        qualificationDegreeOther: "",
                        ...(VENDOR_ELIGIBLE_CATEGORIES.includes(professionalCategory)
                          ? {}
                          : {
                              currentArrangement: "",
                              vendorName: "",
                              facilityName: "",
                              facilityArea: "",
                              dateShiftedToFacility: "",
                              contractStartDate: "",
                              stayRemindersOptIn: "Yes",
                            }),
                      }));
                    }}
                    placeholder="Select category"
                    options={PROFESSIONAL_CATEGORIES}
                  />
                  <FSelect
                    label="Qualification / Degree"
                    req
                    value={form.qualificationDegree || ""}
                    onChange={(e) => {
                      const qualificationDegree = e.target.value;
                      setForm((prev) => ({
                        ...prev,
                        qualificationDegree,
                        qualificationDegreeOther: qualificationDegree === "Other" ? prev.qualificationDegreeOther || "" : "",
                      }));
                    }}
                    placeholder="Select qualification"
                    options={qualificationOptions}
                  />
                  {showQualificationOther ? (
                    <FInput
                      label="Other Qualification / Degree"
                      req
                      {...inp("qualificationDegreeOther")}
                      placeholder="Enter qualification / degree"
                    />
                  ) : null}
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
                    Welfare & Current Stay Arrangement
                  </h3>
                  {showStayArrangementWorkflow ? (
                    <FSelect
                      label="Current Stay Arrangement"
                      req
                      value={form.currentArrangement || ""}
                      onChange={(e) => {
                        const currentArrangement = e.target.value;
                        setForm((prev) => ({
                          ...prev,
                          currentArrangement,
                          ...(currentArrangement === "Embassy Contracted / Arranged"
                            ? { vendorName: prev.vendorName || "AJA Care" }
                            : {
                                vendorName: "",
                                facilityName: "",
                                dateShiftedToFacility: "",
                                contractStartDate: "",
                                stayRemindersOptIn: "Yes",
                              }),
                        }));
                      }}
                      placeholder="Select"
                      options={CURRENT_ARRANGEMENTS}
                    />
                  ) : null}
                  {showVendorSelection ? (
                    <div
                      style={{
                        marginTop: 12,
                        padding: 14,
                        background: T.surfaceLow,
                        border: `1px solid ${T.borderLt}`,
                        borderRadius: 10,
                      }}
                    >
                      <h4 style={{ fontSize: 13, color: T.navy, fontWeight: 800, marginBottom: 12 }}>
                        Current Stay Arrangement Details
                      </h4>
                      <Grid cols={2} gap={14}>
                        <FSelect
                          label="Approved Vendor / Service Provider"
                          value={form.vendorName || "AJA Care"}
                          onChange={(e) => set("vendorName", e.target.value)}
                          options={APPROVED_VENDOR_OPTIONS}
                        />
                        <FInput label="Facility / Building Name" {...inp("facilityName")} placeholder="Building or facility name" />
                        <FInput label="Date shifted to facility" {...inp("dateShiftedToFacility")} type="date" />
                        <FInput label="Contract / stay period start date" {...inp("contractStartDate")} type="date" />
                        <FSelect
                          label="Receive reminders about leaving notice timelines?"
                          value={form.stayRemindersOptIn || "Yes"}
                          onChange={(e) => set("stayRemindersOptIn", e.target.value)}
                          options={["Yes", "No"]}
                        />
                      </Grid>
                    </div>
                  ) : null}
                  {showAreaField ? (
                    <FInput label="Area" {...inp("facilityArea")} placeholder="Area in Kuwait" />
                  ) : null}
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
                    number). You will sign in with your email or passport number (or Civil ID if you add one later).
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
                        const professionalCategory = form.professionalCategory || "";
                        const qualificationDegree = form.qualificationDegree || "";
                        const qualificationDegreeOther = (form.qualificationDegreeOther || "").trim();
                        const categoryVendorEligible = VENDOR_ELIGIBLE_CATEGORIES.includes(professionalCategory);
                        if (!qualificationDegree) {
                          setSubmitError("Qualification / Degree is required.");
                          return;
                        }
                        if (qualificationDegree === "Other" && !qualificationDegreeOther) {
                          setSubmitError("Other Qualification / Degree is required when Qualification / Degree is Other.");
                          return;
                        }
                        if (categoryVendorEligible && !(form.currentArrangement || "").trim()) {
                          setSubmitError("Current Stay Arrangement is required for Nurse / Other Health Worker.");
                          return;
                        }
                        const arrangement = categoryVendorEligible ? form.currentArrangement || "" : "";
                        const arrangementFlag = categoryVendorEligible && /embassy/i.test(arrangement) ? "Yes" : "No";
                        const includeFacilityWorkflow = categoryVendorEligible && arrangement === "Embassy Contracted / Arranged";
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
                            civil_id: (form.civilId || "").trim(),
                            cnic: form.cnic,
                            mobile: form.phone,
                            email: form.email,
                            arrival_date: form.arrivalDate,
                            batch_number: form.batchNumber,
                            hospital: form.hospital,
                            designation: form.jobTitle,
                            professional_category: professionalCategory,
                            qualification_degree: qualificationDegree,
                            qualification_degree_other: qualificationDegree === "Other" ? qualificationDegreeOther : "",
                            current_arrangement: arrangement,
                            degree_type: form.dept || "",
                            remarks: form.remarks || "",
                            ["current_" + "accom" + "modation"]: arrangement,
                            ["applying_for_" + "accom" + "modation"]: arrangementFlag,
                            vendor_name: includeFacilityWorkflow ? (form.vendorName || "AJA Care") : "",
                            facility_name: includeFacilityWorkflow ? (form.facilityName || "") : "",
                            facility_area: categoryVendorEligible ? (form.facilityArea || "") : "",
                            date_shifted_to_facility: includeFacilityWorkflow ? (form.dateShiftedToFacility || "") : "",
                            contract_start_date: includeFacilityWorkflow ? (form.contractStartDate || "") : "",
                            stay_period_start_date: includeFacilityWorkflow ? (form.contractStartDate || "") : "",
                            stay_reminders_opt_in: includeFacilityWorkflow ? (form.stayRemindersOptIn || "Yes") : "",
                            receive_notice_reminders: includeFacilityWorkflow ? (form.stayRemindersOptIn || "Yes") : "",
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
