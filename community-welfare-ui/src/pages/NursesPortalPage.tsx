import { type ReactNode, useEffect, useEffectEvent, useMemo, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { StatusBadge } from "../components/StatusBadge";
import { api, BACKEND_PORTAL } from "../lib/api";
import {
  addLocalPortalRequest,
  buildPortalContextFromApiData,
  clearNursePortal,
  getLocalPortalRequests,
  getNursePortal,
  setNursePortal,
  type NursePortalContext,
} from "../lib/nursePortal";

type PortalTab = "overview" | "stay" | "complaint" | "grading" | "onboarding" | "leaving" | "requests" | "password";

type OnboardingStep = {
  step_code: string;
  step_name: string;
  short_guidance?: string;
  sort_order?: number;
  expected_days_after_arrival?: number;
};

type OnboardingProgress = {
  has_row?: boolean;
  current_stage_code?: string;
  issue_status?: string;
  nurse_note?: string;
  progress_percent?: number;
  completed_steps_count?: number;
  total_steps_count?: number;
  help_needed?: boolean;
  last_updated_at?: string;
  current_step_name?: string;
  current_step_guidance?: string;
  next_step_code?: string;
  next_step_name?: string;
  next_step_guidance?: string;
};

type OnboardingHelpRequest = {
  id?: number;
  status?: string;
  issue_note?: string;
  assigned_to?: string;
  assigned_role?: string;
  created_at?: string;
  updated_at?: string;
  escalation_note?: string;
};

type OnboardingSummaryResponse = {
  success?: boolean;
  feature_enabled?: boolean;
  steps?: OnboardingStep[];
  progress?: OnboardingProgress;
  open_help_request?: OnboardingHelpRequest | null;
  latest_help_request?: OnboardingHelpRequest | null;
  error?: string;
};
type GradingMode = "MARKS" | "PERCENT" | "GPA";

type GradingIdentity = {
  full_name?: string;
  father_name?: string;
  mton_number?: string;
  passport_number?: string;
  cnic?: string;
  civil_id?: string;
  mobile?: string;
  whatsapp?: string;
  email?: string;
  gender?: string;
  workplace?: string;
  qualification_degree?: string;
  qualification_degree_other?: string;
};

type GradingApplication = {
  id?: number;
  ref_no?: string;
  reference?: string;
  status?: string;
  qualification_code?: string;
  qualification_other?: string;
  qualification_label?: string;
  degree_title?: string;
  student_no?: string;
  student_identifier_type?: string;
  student_no_label?: string;
  institute?: string;
  university?: string;
  year_of_passing?: number | string;
  mode?: string;
  total_marks?: number | string | null;
  obtained_marks?: number | string | null;
  entered_percentage?: number | string | null;
  entered_gpa?: number | string | null;
  final_percentage?: number | null;
  final_grade_label?: string;
  submitted_at?: string;
  created_at?: string;
  correction_notes?: string;
  can_nurse_edit?: boolean;
  can_nurse_cancel?: boolean;
};

type GradingSummaryResponse = {
  success?: boolean;
  profile?: GradingIdentity;
  active_application?: GradingApplication | null;
  applications?: GradingApplication[];
  history?: GradingApplication[];
  error?: string;
};

type GradingFormState = {
  application_id: number | null;
  qualification_code: string;
  degree_title: string;
  student_identifier_type: string;
  student_no: string;
  institute: string;
  university: string;
  year_of_passing: string;
  mode: GradingMode;
  total_marks: string;
  obtained_marks: string;
  entered_percentage: string;
  entered_gpa: string;
  declaration_accepted: boolean;
  preview_confirmed: boolean;
};

type ProfileFormState = {
  father_name: string;
  email: string;
  primary_mobile: string;
  whatsapp: string;
  civil_id: string;
  cnic: string;
  mton_number: string;
  qualification_degree: string;
  qualification_degree_other: string;
  workplace: string;
};

const DASH_VALUE = "—";
const GRADING_SUMMARY_FALLBACK = "Could not load grading letter status. Please try again.";
const GRADING_SUBMIT_FALLBACK =
  "Request could not be submitted. Please check your connection and try again. If the problem continues, contact the Embassy.";
const GRADING_MTON_FALLBACK = "MTON number could not be saved. Please check your connection and try again.";
const GRADING_QUALIFICATIONS = [
  { value: "BSN_4Y", label: "BSN Nursing 4 Years" },
  { value: "POST_RN_BSN", label: "Post RN BSN" },
  { value: "GENERAL_NURSING_DIPLOMA", label: "General Nursing Diploma" },
  { value: "SPECIALIZATION_MIDWIFERY", label: "Specialization / Midwifery" },
];
const GRADING_ALLOWED_QUALIFICATION_CODES = new Set(GRADING_QUALIFICATIONS.map((item) => item.value));
const GRADING_IDENTIFIER_TYPES = [
  "Student Number",
  "Seat Number",
  "Registration Number",
  "Enrollment Number",
  "Roll Number",
] as const;
const GRADING_IDENTIFIER_TYPE_SET = new Set<string>(GRADING_IDENTIFIER_TYPES);
const PROFILE_QUALIFICATION_OPTIONS = [
  "Diploma Nurse",
  "BSN Nursing",
  "Doctor MBBS",
  "Doctor BDS",
  "Other",
] as const;

function normalizeMtonNumber(value: string) {
  const raw = (value || "").trim().toUpperCase();
  if (!raw) return "";
  const match = raw.match(/^MTON[\s-]*E[\s-]*(\d{1,6})$/);
  return match ? `MTON-E-${match[1]}` : raw.replace(/\s+/g, " ");
}

function isValidMtonNumber(value: unknown) {
  return /^MTON-E-\d{1,6}$/.test(String(value || "").trim().toUpperCase());
}

function normalizeQualificationCode(code: string) {
  const normalized = (code || "").trim().toUpperCase();
  if (normalized === "MIDWIFERY_ADDITIONAL") return "SPECIALIZATION_MIDWIFERY";
  return normalized;
}

function normalizeGradingIdentifierType(value: string) {
  const raw = (value || "").trim().toLowerCase();
  const match = GRADING_IDENTIFIER_TYPES.find((label) => label.toLowerCase() === raw);
  return match || "Student Number";
}

function normalizeRequestError(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : "";
  if (!message || /failed to fetch|networkerror|load failed/i.test(message)) {
    return fallback;
  }
  return message;
}

function displayValue(value: unknown) {
  const text = String(value ?? "").trim();
  return text || DASH_VALUE;
}

function normalizeArrivalBatchNumber(value: unknown) {
  const match = String(value ?? "").trim().match(/\d+/);
  return match ? match[0] : "";
}

function qualificationLabelFromCode(code: string, other = "") {
  const normalized = normalizeQualificationCode(code);
  if (normalized === "OTHER") return other || "Other (Legacy)";
  if (normalized === "NURSING_DIPLOMA") return "Nursing Diploma (Legacy)";
  return GRADING_QUALIFICATIONS.find((item) => item.value === normalized)?.label || code || DASH_VALUE;
}

function createGradingForm(application?: GradingApplication | null): GradingFormState {
  const qualificationCode = normalizeQualificationCode(application?.qualification_code || "");
  return {
    application_id: typeof application?.id === "number" ? application.id : null,
    qualification_code: GRADING_ALLOWED_QUALIFICATION_CODES.has(qualificationCode) ? qualificationCode : "",
    degree_title: application?.degree_title || "",
    student_identifier_type: normalizeGradingIdentifierType(
      application?.student_identifier_type || application?.student_no_label || ""
    ),
    student_no: application?.student_no || "",
    institute: application?.institute || "",
    university: application?.university || "",
    year_of_passing: application?.year_of_passing ? String(application.year_of_passing) : "",
    mode: (application?.mode as GradingMode) || "MARKS",
    total_marks: application?.total_marks == null ? "" : String(application.total_marks),
    obtained_marks: application?.obtained_marks == null ? "" : String(application.obtained_marks),
    entered_percentage: application?.entered_percentage == null ? "" : String(application.entered_percentage),
    entered_gpa: application?.entered_gpa == null ? "" : String(application.entered_gpa),
    declaration_accepted: false,
    preview_confirmed: false,
  };
}

function createProfileForm(ctx: NursePortalContext): ProfileFormState {
  return {
    father_name: ctx.fatherName || "",
    email: ctx.email || "",
    primary_mobile: ctx.mobileFull || ctx.mobile || "",
    whatsapp: ctx.whatsappFull || ctx.mobileFull || ctx.mobile || "",
    civil_id: ctx.civilId || "",
    cnic: ctx.cnic || "",
    mton_number: normalizeMtonNumber(ctx.mtonNumber || ""),
    qualification_degree: ctx.qualificationDegree || "",
    qualification_degree_other: ctx.qualificationDegreeOther || "",
    workplace: ctx.hospital || "",
  };
}

function gradingSummaryPath(ctx: NursePortalContext) {
  const params = new URLSearchParams();
  if (ctx.referenceId) params.set("nurse_reference_id", ctx.referenceId);
  if (ctx.passportNumber) params.set("passport_number", ctx.passportNumber);
  if (ctx.mobile || ctx.civilId) params.set("verifier", ctx.mobile || ctx.civilId);
  if (ctx.sessionMarker) params.set("session_marker", ctx.sessionMarker);
  return `/api/nurses/grading-letter/summary?${params.toString()}`;
}

function onboardingSummaryPath(ctx: NursePortalContext) {
  const params = new URLSearchParams();
  if (ctx.referenceId) params.set("nurse_reference_id", ctx.referenceId);
  if (ctx.passportNumber) params.set("passport_number", ctx.passportNumber);
  if (ctx.mobile || ctx.civilId) params.set("verifier", ctx.mobile || ctx.civilId);
  if (ctx.sessionMarker) params.set("session_marker", ctx.sessionMarker);
  return `/api/nurses/onboarding/summary?${params.toString()}`;
}

function onboardingIdentityPayload(ctx: NursePortalContext) {
  return {
    nurse_reference_id: ctx.referenceId,
    passport_number: ctx.passportNumber,
    verifier: ctx.mobile || ctx.civilId || "",
    session_marker: ctx.sessionMarker,
  };
}

function prettifyOnboardingHelpStatus(status: string) {
  if (!status) return "";
  return status
    .toLowerCase()
    .split("_")
    .map((part) => (part ? part.charAt(0).toUpperCase() + part.slice(1) : part))
    .join(" ");
}

function gradingGradeLabel(percentage: number) {
  if (percentage >= 80) return "Excellent";
  if (percentage >= 70) return "Very Good";
  if (percentage >= 60) return "Good";
  if (percentage >= 50) return "Pass";
  return "Fail";
}

function prettifyGradingStatus(status: string) {
  return status
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function gradingStatusType(status: string) {
  const normalized = status.toUpperCase();
  if (normalized === "ISSUED") return "resolved";
  if (normalized === "REJECTED" || normalized === "CANCELLED") return "rejected";
  if (normalized === "CORRECTION_REQUIRED") return "urgent";
  if (normalized === "APPROVED" || normalized === "LETTER_GENERATED" || normalized === "UNDER_REVIEW") return "processing";
  return "pending";
}

function formatGradingPercent(value: number | string | null | undefined) {
  const num = Number(value);
  return Number.isFinite(num) ? `${num.toFixed(2)}%` : DASH_VALUE;
}

function computeGradingPreview(form: GradingFormState) {
  const commonComplete =
    !!form.qualification_code.trim() &&
    !!form.degree_title.trim() &&
    !!form.student_identifier_type.trim() &&
    !!form.student_no.trim() &&
    !!form.institute.trim() &&
    !!form.university.trim() &&
    !!form.year_of_passing.trim();

  if (!GRADING_IDENTIFIER_TYPE_SET.has(form.student_identifier_type.trim())) {
    return {
      percentage: null,
      gradeLabel: DASH_VALUE,
      validationMessage: "Please select a valid identifier type.",
      canSubmit: false,
    };
  }

  let percentage: number | null = null;
  let validationMessage = "";

  if (form.mode === "MARKS") {
    const totalRaw = form.total_marks.trim();
    const obtainedRaw = form.obtained_marks.trim();
    if (totalRaw || obtainedRaw) {
      const total = Number(totalRaw);
      const obtained = Number(obtainedRaw);
      if (!Number.isFinite(total) || total <= 0) {
        validationMessage = "Total marks must be greater than zero.";
      } else if (!Number.isFinite(obtained) || obtained < 0 || obtained > total) {
        validationMessage = "Obtained marks cannot exceed total marks.";
      } else {
        percentage = (obtained / total) * 100;
      }
    }
  } else if (form.mode === "PERCENT") {
    const percentRaw = form.entered_percentage.trim();
    if (percentRaw) {
      const percent = Number(percentRaw);
      if (!Number.isFinite(percent) || percent < 0 || percent > 100) {
        validationMessage = "Percentage must be between 0 and 100.";
      } else {
        percentage = percent;
      }
    }
  } else {
    const gpaRaw = form.entered_gpa.trim();
    if (gpaRaw) {
      const gpa = Number(gpaRaw);
      if (!Number.isFinite(gpa) || gpa < 0 || gpa > 4) {
        validationMessage = "GPA cannot exceed 4.00.";
      } else {
        percentage = (gpa / 4) * 100;
      }
    }
  }

  if (percentage != null) {
    percentage = Number(percentage.toFixed(2));
  }

  const modeReady =
    form.mode === "MARKS"
      ? !!form.total_marks.trim() && !!form.obtained_marks.trim()
      : form.mode === "PERCENT"
        ? !!form.entered_percentage.trim()
        : !!form.entered_gpa.trim();

  if (!validationMessage && commonComplete && modeReady && percentage != null && !form.preview_confirmed) {
    validationMessage = "Please review the preview and confirm the information before submission.";
  }
  if (!validationMessage && commonComplete && modeReady && percentage != null && !form.declaration_accepted) {
    validationMessage = "Please accept the declaration before submission.";
  }

  return {
    percentage,
    gradeLabel: percentage != null ? gradingGradeLabel(percentage) : DASH_VALUE,
    validationMessage,
    canSubmit:
      commonComplete &&
      modeReady &&
      form.declaration_accepted &&
      form.preview_confirmed &&
      percentage != null &&
      !validationMessage,
  };
}

function parentRelationForGender(gender?: string) {
  const normalized = (gender || "").trim().toLowerCase();
  if (normalized === "male" || normalized === "m" || normalized === "man" || normalized === "boy") {
    return "S/o";
  }
  if (normalized === "female" || normalized === "f" || normalized === "woman" || normalized === "girl") {
    return "D/o";
  }
  return "S/o/D/o";
}

function qualificationSubtitleFromForm(_form: GradingFormState) {
  // Per accepted Embassy sample: never auto-add a parenthetical that duplicates
  // the qualification (e.g., "BSN Nursing" + "(Post RN BSN)"). The degree
  // title is the canonical label; an explicit subtype like "(Generic)" must be
  // entered into degree_title itself by the applicant or admin.
  return "";
}

function gradingModeSummary(form: GradingFormState) {
  if (form.mode === "MARKS") {
    return form.total_marks.trim() && form.obtained_marks.trim()
      ? `Marks: ${form.obtained_marks.trim()} out of ${form.total_marks.trim()}`
      : "Marks: —";
  }
  if (form.mode === "PERCENT") {
    return form.entered_percentage.trim() ? `Entered percentage: ${form.entered_percentage.trim()}%` : "Entered percentage: —";
  }
  return form.entered_gpa.trim() ? `GPA: ${form.entered_gpa.trim()} out of 4.00` : "GPA: —";
}

function buildGradingPreviewLetterModel(
  ctx: NursePortalContext,
  profile: GradingIdentity,
  form: GradingFormState,
  computed: ReturnType<typeof computeGradingPreview>
) {
  const applicantName = (profile.full_name || ctx.fullName || "").trim() || DASH_VALUE;
  const fatherName = (profile.father_name || ctx.fatherName || "").trim() || DASH_VALUE;
  const passportNumber = (profile.passport_number || ctx.passportNumber || "").trim() || DASH_VALUE;
  const degreeTitle = form.degree_title.trim() || DASH_VALUE;
  const identifierLabel = normalizeGradingIdentifierType(form.student_identifier_type || "Student Number")
    .replace("Number", "No.");
  return {
    applicantName,
    fatherName,
    relationText: `${parentRelationForGender(profile.gender || ctx.gender)} ${fatherName}`,
    passportNumber,
    degreeTitle,
    qualificationSubtitle: qualificationSubtitleFromForm(form),
    identifierLabel,
    identifierValue: form.student_no.trim() || DASH_VALUE,
    institute: form.institute.trim() || DASH_VALUE,
    university: form.university.trim() || DASH_VALUE,
    yearOfPassing: form.year_of_passing.trim() || DASH_VALUE,
    finalPercentage: computed.percentage != null ? `${computed.percentage.toFixed(2)}%` : DASH_VALUE,
    finalGradeLabel: computed.gradeLabel || DASH_VALUE,
    finalResultText:
      computed.percentage != null && computed.gradeLabel && computed.gradeLabel !== DASH_VALUE
        ? `${computed.percentage.toFixed(2)}% "${computed.gradeLabel}"`
        : DASH_VALUE,
    cnic: (profile.cnic || ctx.cnic || "").trim() || DASH_VALUE,
    civilId: (profile.civil_id || ctx.civilId || "").trim() || DASH_VALUE,
    mobile: (profile.mobile || ctx.mobileFull || ctx.mobile || "").trim() || DASH_VALUE,
    whatsapp: (profile.whatsapp || ctx.whatsappFull || ctx.mobileFull || ctx.mobile || "").trim() || DASH_VALUE,
    email: (profile.email || ctx.email || "").trim() || DASH_VALUE,
    mtonNumber: normalizeMtonNumber(profile.mton_number || ctx.mtonNumber || "") || DASH_VALUE,
    qualificationType: qualificationLabelFromCode(form.qualification_code || "", ""),
    gradingMode: form.mode,
    gradingModeSummary: gradingModeSummary(form),
    workplace: (profile.workplace || ctx.hospital || "").trim() || DASH_VALUE,
  };
}

function OfficialLetterPreview(props: {
  ctx: NursePortalContext;
  profile: GradingIdentity;
  form: GradingFormState;
  computed: ReturnType<typeof computeGradingPreview>;
}) {
  const letter = buildGradingPreviewLetterModel(props.ctx, props.profile, props.form, props.computed);
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div
        className="grading-preview-print-hide"
        style={{
          border: "1px solid #D9E2EC",
          borderRadius: 12,
          background: "#F8FAFC",
          padding: 14,
          display: "grid",
          gap: 10,
        }}
      >
        <div style={{ fontWeight: 700, color: "#2D4A6B" }}>Application details for internal review</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 10 }}>
          <Field label="CNIC" value={letter.cnic} />
          <Field label="Civil ID" value={letter.civilId} />
          <Field label="MOH / MTON Number" value={letter.mtonNumber} />
          <Field label="Primary Mobile" value={letter.mobile} />
          <Field label="WhatsApp" value={letter.whatsapp} />
          <Field label="Email" value={letter.email} />
          <Field label="Qualification Type" value={letter.qualificationType} />
          <Field label="Grading Mode" value={letter.gradingMode} />
          <Field label="Marks / GPA / %" value={letter.gradingModeSummary} />
          <Field label="Computed Percentage" value={letter.finalPercentage} />
          <Field label="Provisional Grade" value={letter.finalGradeLabel} />
          <Field label="Current Workplace / Hospital" value={letter.workplace} />
        </div>
      </div>

      <div
        role="note"
        style={{
          background: "#FEF3C7",
          border: "1px solid #FDE68A",
          color: "#7c2d12",
          borderRadius: 10,
          padding: "10px 12px",
          fontSize: 13,
          lineHeight: 1.55,
          maxWidth: 794,
          margin: "0 auto",
        }}
      >
        This preview is not an official Embassy letter and cannot be used for MOH or any other official purpose.
        It is only for checking spelling and data before submission.
        <br />
        <span dir="rtl">هذه نسخة معاينة فقط وليست كتاباً رسمياً ولا تصلح للاستخدام لدى وزارة الصحة أو أي جهة رسمية.</span>
      </div>

      <div
        className="grading-letter-page grading-preview-shell"
        style={{
          position: "relative",
          background: "#fff",
          border: "1px solid #D9E2EC",
          borderRadius: 6,
          padding: "54px 56px 36px",
          color: "#000",
          overflow: "hidden",
          boxShadow: "0 18px 44px rgba(15, 23, 42, 0.08)",
          fontFamily: '"Times New Roman", Georgia, serif',
          width: "100%",
          maxWidth: 794,
          minHeight: 1123,
          margin: "0 auto",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            zIndex: 0,
          }}
        >
          <div
            style={{
              transform: "rotate(-28deg)",
              textAlign: "center",
              fontSize: "clamp(28px, 5.4vw, 52px)",
              fontWeight: 800,
              letterSpacing: "0.06em",
              color: "rgba(185, 28, 28, 0.16)",
              lineHeight: 1.25,
            }}
          >
            NOT OFFICIAL FOR MOH USE
            <br />
            PREVIEW ONLY
            <br />
            <span dir="rtl" style={{ fontSize: "0.7em" }}>غير رسمي ولا يستخدم لدى وزارة الصحة</span>
            <br />
            <span dir="rtl" style={{ fontSize: "0.7em" }}>للمراجعة فقط</span>
          </div>
        </div>

        <div style={{ position: "relative", zIndex: 1, flex: "1 1 auto" }}>
          <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 12, alignItems: "start" }}>
            <div style={{ display: "flex", justifyContent: "flex-start" }}>
              <img
                src="/images/gop-emblem.png"
                alt="Government of Pakistan emblem"
                style={{ width: 84, height: "auto", objectFit: "contain", display: "block" }}
              />
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 19, fontWeight: 700, lineHeight: 1.2 }}>
                Embassy of Islamic Republic of Pakistan
                <br />
                Kuwait
              </div>
              <div dir="rtl" style={{ marginTop: 6, fontSize: 17, fontWeight: 700, lineHeight: 1.35 }}>
                سفارة جمهورية باكستان الإسلامية
                <br />
                الكويت
              </div>
            </div>
          </div>

          <div style={{ marginTop: 24, fontSize: 16 }}>No. Pol-II/18/2021 (Attestation)</div>

          <div style={{ margin: "22px 0 16px", textAlign: "center", fontSize: 20, fontWeight: 700, textDecoration: "underline" }}>
            TO WHOM IT MAY CONCERN
          </div>

          <div style={{ fontSize: 16, lineHeight: 1.85, maxWidth: 680, margin: "0 auto 16px" }}>
            This is to certify that according to the documents produced in this Embassy, {letter.applicantName}
            <br />
            {letter.relationText} and holding Pakistani Passport No. {letter.passportNumber}, passed
            <br />
            the examination of:
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))",
              gap: 18,
              margin: "18px 0 22px",
              textAlign: "center",
              fontSize: 16,
              lineHeight: 1.45,
            }}
          >
            <div>
              <div>{letter.degreeTitle}</div>
              {letter.qualificationSubtitle ? <div>({letter.qualificationSubtitle})</div> : null}
              <div>{letter.identifierLabel} {letter.identifierValue}</div>
            </div>
            <div>
              <div>{letter.institute}</div>
              <div>Affiliated with {letter.university}</div>
              <div>{letter.yearOfPassing}</div>
              <div>{letter.finalResultText}</div>
            </div>
          </div>

          <div style={{ fontSize: 16, lineHeight: 1.85, maxWidth: 680, margin: "0 auto" }}>
            This certificate is issued on the request of the applicant without any liability on the part
            <br />
            of this Embassy whatsoever.
          </div>
        </div>

        <div
          style={{
            position: "relative",
            zIndex: 1,
            marginTop: "auto",
            borderTop: "1px solid #111",
            paddingTop: 10,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))",
            gap: 8,
            fontSize: 14,
          }}
        >
          <div>Telephone: 00965-25354073/25327651</div>
          <div style={{ textAlign: "center" }}>Fax: 00965-25327648</div>
          <div style={{ textAlign: "right" }}>Email: parepkuwait@mofa.gov.pk</div>
        </div>
      </div>
    </div>
  );
}

function buildPendingArrivalFeatureMessage(baseMessage: string, featureName: string) {
  const headline = baseMessage.trim() || "Your nurse portal account is pending arrival activation.";
  return `${headline} ${featureName} will open after the Embassy marks your arrival batch as ARRIVED.`;
}

export function NursesPortalPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const locationPortalContext =
    (location.state as { portalContext?: NursePortalContext } | null)?.portalContext || null;
  const [ctx, setCtx] = useState<NursePortalContext | null>(() => locationPortalContext || getNursePortal());
  const [requests, setRequests] = useState(() => getLocalPortalRequests());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [qualificationInfo, setQualificationInfo] = useState({ degree: "", other: "" });
  const [currentEmail, setCurrentEmail] = useState(ctx?.email || "");
  const [currentEmailStatus, setCurrentEmailStatus] = useState(ctx?.emailStatus || "");
  const [gradingSummary, setGradingSummary] = useState<GradingSummaryResponse | null>(null);
  const [gradingLoading, setGradingLoading] = useState(false);
  const [gradingError, setGradingError] = useState("");
  const [gradingFlash, setGradingFlash] = useState("");
  const [gradingSubmitBusy, setGradingSubmitBusy] = useState(false);
  const [gradingMtonInput, setGradingMtonInput] = useState(() => normalizeMtonNumber(ctx?.mtonNumber || ""));
  const [gradingMtonBusy, setGradingMtonBusy] = useState(false);
  const [gradingMtonError, setGradingMtonError] = useState("");
  const [gradingMtonFlash, setGradingMtonFlash] = useState("");
  const [gradingForm, setGradingForm] = useState<GradingFormState>(() => createGradingForm());
  const [showProfileEditor, setShowProfileEditor] = useState(false);
  const [profileForm, setProfileForm] = useState<ProfileFormState>(() => (ctx ? createProfileForm(ctx) : {
    father_name: "",
    email: "",
    primary_mobile: "",
    whatsapp: "",
    civil_id: "",
    cnic: "",
    mton_number: "",
    qualification_degree: "",
    qualification_degree_other: "",
    workplace: "",
  }));
  const [profileSaveBusy, setProfileSaveBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileFlash, setProfileFlash] = useState("");

  const [facilityReq, setFacilityReq] = useState({
    category: "",
    urgency: "Normal",
    subject: "",
    details: "",
    preferred_contact_method: "WhatsApp",
  });
  const [stay, setStay] = useState(() => ({
    confirmation_option: "",
    current_facility_name: ctx?.facilityRoster?.facility_name || "",
    area: ctx?.facilityRoster?.facility_area || ctx?.facilityRoster?.area || "",
    room_number: ctx?.facilityRoster?.room_number || "",
    bed_number: ctx?.facilityRoster?.bed_number || "",
    current_phone: ctx?.mobileFull || ctx?.mobile || "",
    preferred_contact_method: "WhatsApp",
    remarks: "",
  }));
  const [complaint, setComplaint] = useState({ complaint_category: "", priority: "Normal", subject: "", description: "" });
  const [leaving, setLeaving] = useState({
    current_facility: ctx?.facilityRoster?.facility_name || "",
    date_shifted_to_facility: ctx?.facilityRoster?.date_shifted_to_facility || "",
    intended_leaving_date: "",
    reason_category: "",
    new_stay_arrangement: "",
    new_area: "",
    assistance_required: "No",
    remarks: "",
  });
  const [curPwd, setCurPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmNew, setConfirmNew] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [onboardingSummary, setOnboardingSummary] = useState<OnboardingSummaryResponse | null>(null);
  const [onboardingLoading, setOnboardingLoading] = useState(false);
  const [onboardingError, setOnboardingError] = useState("");
  const [onboardingFlash, setOnboardingFlash] = useState("");
  const [onboardingBusy, setOnboardingBusy] = useState(false);
  const [onboardingForm, setOnboardingForm] = useState<{ current_stage_code: string; issue_status: string; nurse_note: string }>(
    { current_stage_code: "", issue_status: "NO_ISSUE", nurse_note: "" }
  );

  function commitPortalContext(next: NursePortalContext | ((prev: NursePortalContext) => NursePortalContext)) {
    setCtx((prev) => {
      if (!prev) return prev;
      const resolved = typeof next === "function" ? next(prev) : next;
      setNursePortal(resolved);
      return resolved;
    });
  }

  if (!ctx) {
    navigate("/nurses/login", { replace: true });
    return null;
  }

  const isDoctor = (ctx.professionalCategory || "").toLowerCase() === "doctor";
  const tab = (params.get("tab") || "overview") as PortalTab;
  const tabs = isDoctor
    ? (["overview", "complaint", "grading", "onboarding", "requests", "password"] as PortalTab[])
    : (["overview", "stay", "complaint", "grading", "onboarding", "leaving", "requests", "password"] as PortalTab[]);
  const activeTab = tabs.includes(tab) ? tab : "overview";
  const pagePadding = "clamp(16px, 4vw, 24px)";
  const overviewGridColumns = "repeat(auto-fit,minmax(320px,1fr))";
  const detailGridColumns = "repeat(auto-fit,minmax(180px,1fr))";
  const compactGridColumns = "repeat(auto-fit,minmax(160px,1fr))";

  const statusType = (ctx.registrationStatus || "").toLowerCase().includes("resolved")
    ? "resolved"
    : (ctx.registrationStatus || "").toLowerCase().includes("progress")
    ? "processing"
    : "pending";
  const vendorName = ctx.facilityRoster?.vendor_name?.trim() || "";
  const approvedVendorLabel = ctx.facilityRoster?.approved_vendor_label || (vendorName ? `Approved Vendor: ${vendorName}` : "Approved Vendor: To be confirmed");
  const currentArrangement = (ctx.facilityRoster?.current_arrangement || "").trim();
  const hasEmbassyArrangement = !isDoctor && currentArrangement === "Embassy Contracted / Arranged";
  const isMohHotel = !isDoctor && currentArrangement === "MOH Provided Hotel - Arrival Stay";
  const mohHotelName = (ctx.facilityRoster as any)?.moh_hotel_name || "";
  const mohHotelArea = (ctx.facilityRoster as any)?.moh_hotel_area || "";
  const mohHotelStartDate = (ctx.facilityRoster as any)?.moh_hotel_start_date || "";
  const mohHotelExpectedEndDate = (ctx.facilityRoster as any)?.moh_hotel_expected_end_date || "";
  const mohHotelDurationMonths = (ctx.facilityRoster as any)?.moh_hotel_duration_months || 3;
  const showStaySummary = !isDoctor && !!currentArrangement;
  const stayArea = ctx.facilityRoster?.facility_area || ctx.facilityRoster?.area || "";
  const stayReminderPref = (ctx.facilityRoster as any)?.receive_notice_reminders || (ctx.facilityRoster as any)?.stay_reminders_opt_in || "";
  const monthlyCheckinStatus =
    ctx.facilityRoster?.monthly_checkin_status ||
    ctx.facilityRoster?.latest_monthly_checkin_status ||
    "";
  const monthlyCheckinPending = !!ctx.facilityRoster?.latest_monthly_checkin_pending;
  const monthlyCheckinUrl = ctx.facilityRoster?.latest_monthly_checkin_url
    ? `${BACKEND_PORTAL}${ctx.facilityRoster.latest_monthly_checkin_url}`
    : "";
  const monthlyCheckinReceivedAt =
    ctx.facilityRoster?.last_monthly_checkin_response_at ||
    ctx.facilityRoster?.latest_monthly_checkin_received_at ||
    "";
  const qualificationDisplay = qualificationInfo.degree === "Other"
    ? (qualificationInfo.other || "—")
    : (qualificationInfo.degree || "—");
  const stayArrangementText = `Your current stay arrangement is recorded as Embassy Contracted / Arranged with ${approvedVendorLabel}.`;
  const emailStatus = (currentEmailStatus || "").trim();
  const emailStatusText = emailStatus.toLowerCase() === "verified"
    ? "Email verified. Your portal account is active."
    : emailStatus.toLowerCase().includes("failed")
      ? "Delivery Failed"
      : "Email verification pending. Please verify your email address to activate your portal account and receive official updates.";
  const housingAccount = ctx.housingAccount || null;
  const pendingArrival = Boolean(ctx.pendingArrival || housingAccount?.pendingArrival);
  const pendingArrivalBanner =
    (ctx.pendingArrivalBanner || housingAccount?.portalBanner || "").trim() ||
    "Your nurse portal account is pending arrival activation.";
  const stayAccessBlocked = pendingArrival;
  const complaintAccessBlocked = pendingArrival;
  const gradingAccessBlocked = pendingArrival;
  const leavingAccessBlocked = pendingArrival;
  const stayBlockedMessage = buildPendingArrivalFeatureMessage(
    pendingArrivalBanner,
    "Stay-arrangement services"
  );
  const complaintBlockedMessage = buildPendingArrivalFeatureMessage(
    pendingArrivalBanner,
    "Complaints"
  );
  const gradingBlockedMessage = buildPendingArrivalFeatureMessage(
    pendingArrivalBanner,
    "Grading letter requests"
  );
  const leavingBlockedMessage = buildPendingArrivalFeatureMessage(
    pendingArrivalBanner,
    "Leaving notices and stay-arrangement changes"
  );
  const gradingPreview = useMemo(() => computeGradingPreview(gradingForm), [gradingForm]);
  const gradingActiveRequest = gradingSummary?.active_application || null;
  const gradingHistory = gradingSummary?.applications || gradingSummary?.history || [];
  const gradingProfile = gradingSummary?.profile || {};
  const savedMtonNumber = normalizeMtonNumber(gradingProfile.mton_number || ctx.mtonNumber || "");
  const hasSavedMtonNumber = isValidMtonNumber(savedMtonNumber);
  const canEditActiveGradingRequest = Boolean(gradingActiveRequest?.can_nurse_edit);
  const gradingSubmitLabel = !canEditActiveGradingRequest
    ? "Submit Grading Letter Request"
    : (gradingActiveRequest?.status || "").toUpperCase() === "CORRECTION_REQUIRED"
      ? "Resubmit Corrected Request"
      : "Update Submitted Request";

  const refreshGradingSummary = useEffectEvent(async (showLoading = true) => {
    if (!ctx) return;
    if (showLoading) setGradingLoading(true);
    setGradingError("");
    try {
      const res = await api.get<GradingSummaryResponse>(gradingSummaryPath(ctx));
      if (!res?.success) {
        throw new Error(res?.error || GRADING_SUMMARY_FALLBACK);
      }
      setGradingSummary(res);
      if (res.active_application?.can_nurse_edit) {
        setGradingForm(createGradingForm(res.active_application));
      } else if (res.active_application) {
        setGradingForm(createGradingForm());
      }
    } catch (_error) {
      setGradingSummary(null);
      setGradingError(GRADING_SUMMARY_FALLBACK);
    } finally {
      setGradingLoading(false);
    }
  });

  const refreshOnboardingSummary = useEffectEvent(async (showLoading = true) => {
    if (!ctx) return;
    if (showLoading) setOnboardingLoading(true);
    setOnboardingError("");
    try {
      const res = await api.get<OnboardingSummaryResponse>(onboardingSummaryPath(ctx));
      if (!res?.success) {
        throw new Error(res?.error || "Could not load onboarding status. Please try again.");
      }
      setOnboardingSummary(res);
      const progress = res.progress || {};
      setOnboardingForm({
        current_stage_code: progress.current_stage_code || "",
        issue_status: (progress.issue_status as string) || "NO_ISSUE",
        nurse_note: progress.nurse_note || "",
      });
    } catch (error) {
      setOnboardingSummary(null);
      setOnboardingError(
        (error as Error)?.message || "Could not load onboarding status. Please try again."
      );
    } finally {
      setOnboardingLoading(false);
    }
  });

  async function submitOnboardingUpdate() {
    if (!ctx) return;
    if (!onboardingForm.current_stage_code) {
      setOnboardingError("Please select your current onboarding stage.");
      return;
    }
    setOnboardingBusy(true);
    setOnboardingError("");
    setOnboardingFlash("");
    try {
      const res = await api.post<OnboardingSummaryResponse & { message?: string }>(
        "/api/nurses/onboarding/update",
        {
          ...onboardingIdentityPayload(ctx),
          current_stage_code: onboardingForm.current_stage_code,
          issue_status: onboardingForm.issue_status || "NO_ISSUE",
          nurse_note: onboardingForm.nurse_note || "",
        }
      );
      if (!res?.success) {
        throw new Error(res?.error || "Update could not be saved. Please try again.");
      }
      setOnboardingSummary(res);
      const progress = res.progress || {};
      setOnboardingForm({
        current_stage_code: progress.current_stage_code || "",
        issue_status: (progress.issue_status as string) || "NO_ISSUE",
        nurse_note: progress.nurse_note || "",
      });
      setOnboardingFlash(res.message || "Onboarding status updated.");
    } catch (error) {
      setOnboardingError(
        (error as Error)?.message || "Update could not be saved. Please try again."
      );
    } finally {
      setOnboardingBusy(false);
    }
  }

  useEffect(() => {
    if (!locationPortalContext) return;
    setCtx(locationPortalContext);
    setNursePortal(locationPortalContext);
  }, [locationPortalContext]);

  useEffect(() => {
    setCurrentEmail(ctx.email || "");
    setCurrentEmailStatus(ctx.emailStatus || "");
    setGradingMtonInput(normalizeMtonNumber(ctx.mtonNumber || ""));
    setProfileForm(createProfileForm(ctx));
  }, [ctx]);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const res = await api.post<{ success?: boolean; data?: { qualification_degree?: string; qualification_degree_other?: string } }>(
          "/api/nurses/track",
          {
            identity: ctx.referenceId || ctx.passportNumber,
            verifier: ctx.mobile || ctx.civilId || "",
          }
        );
        if (!live || !res?.success) return;
        const nextCtx = {
          ...buildPortalContextFromApiData(res.data),
          sessionMarker: ctx.sessionMarker,
        };
        commitPortalContext((prev) => ({ ...prev, ...nextCtx }));
        setQualificationInfo({
          degree: (res.data?.qualification_degree || "").toString(),
          other: (res.data?.qualification_degree_other || "").toString(),
        });
      } catch {
        if (!live) return;
      }
    })();
    return () => {
      live = false;
    };
  }, [ctx.referenceId, ctx.passportNumber, ctx.mobile, ctx.civilId, ctx.sessionMarker]);

  useEffect(() => {
    if (activeTab !== "grading" || gradingAccessBlocked) return;
    void refreshGradingSummary();
  }, [activeTab, gradingAccessBlocked]);

  useEffect(() => {
    if (activeTab !== "onboarding") return;
    if (pendingArrival) return;
    void refreshOnboardingSummary();
  }, [activeTab, pendingArrival]);

  async function submitFacilityRequest() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/facility-assistance", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        category: facilityReq.category,
        urgency: facilityReq.urgency,
        subject: facilityReq.subject || facilityReq.category,
        details: facilityReq.details,
        preferred_contact_method: facilityReq.preferred_contact_method,
      });
      addLocalPortalRequest({ type: "Facility Assistance", summary: `Category: ${facilityReq.category || "N/A"}` });
      setRequests(getLocalPortalRequests());
      setMsg("Facility assistance request submitted for Community Welfare Wing review.");
      setFacilityReq({ category: "", urgency: "Normal", subject: "", details: "", preferred_contact_method: "WhatsApp" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit facility assistance request.");
    } finally {
      setBusy(false);
    }
  }

  async function submitStayConfirmation() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/stay-confirmation", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        ...stay,
      });
      addLocalPortalRequest({ type: "Stay Confirmation", summary: "Stay arrangement update submitted." });
      setRequests(getLocalPortalRequests());
      setMsg("Stay arrangement confirmation submitted for Community Welfare Wing review.");
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit stay arrangement confirmation.");
    } finally {
      setBusy(false);
    }
  }

  async function submitComplaint() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/complaint", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        complaint_category: complaint.complaint_category,
        priority: complaint.priority,
        subject: complaint.subject,
        description: complaint.description,
        preferred_contact_method: "WhatsApp",
        consent: true,
      });
      addLocalPortalRequest({ type: "Complaint", summary: `Subject: ${complaint.subject || "N/A"}` });
      setRequests(getLocalPortalRequests());
      setMsg("Complaint submitted. Marked as pending official review.");
      setComplaint({ complaint_category: "", priority: "Normal", subject: "", description: "" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit complaint.");
    } finally {
      setBusy(false);
    }
  }

  async function submitLeavingNotice() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/leave-notice", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        current_facility: leaving.current_facility,
        date_shifted_to_facility: leaving.date_shifted_to_facility,
        intended_leaving_date: leaving.intended_leaving_date,
        reason_category: leaving.reason_category,
        new_stay_arrangement: leaving.new_stay_arrangement,
        new_area: leaving.new_area,
        assistance_required: leaving.assistance_required,
        reason: leaving.remarks,
      });
      addLocalPortalRequest({ type: "Leaving Notice", summary: `Move out date: ${leaving.intended_leaving_date || "N/A"}` });
      setRequests(getLocalPortalRequests());
      setMsg("Leaving notice submitted for Community Welfare Wing review.");
      setLeaving({ current_facility: ctx.facilityRoster?.facility_name || "", date_shifted_to_facility: ctx.facilityRoster?.date_shifted_to_facility || "", intended_leaving_date: "", reason_category: "", new_stay_arrangement: "", new_area: "", assistance_required: "No", remarks: "" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit leaving notice.");
    } finally {
      setBusy(false);
    }
  }

  async function submitGradingLetter() {
    setGradingSubmitBusy(true);
    setGradingError("");
    setGradingFlash("");

    if (!hasSavedMtonNumber) {
      setGradingError("Please enter your MOH / MTON number before submitting a grading letter request.");
      setGradingSubmitBusy(false);
      return;
    }

    if (!gradingPreview.canSubmit) {
      setGradingError(gradingPreview.validationMessage || "Please complete all required grading letter fields.");
      setGradingSubmitBusy(false);
      return;
    }

    const payload = {
      nurse_reference_id: ctx.referenceId,
      passport_number: ctx.passportNumber,
      verifier: ctx.mobile || ctx.civilId || "",
      session_marker: ctx.sessionMarker || "",
      id: gradingForm.application_id || undefined,
      qualification_code: gradingForm.qualification_code,
      qualification_other: "",
      degree_title: gradingForm.degree_title.trim(),
      student_identifier_type: gradingForm.student_identifier_type.trim(),
      student_no: gradingForm.student_no.trim(),
      institute: gradingForm.institute.trim(),
      university: gradingForm.university.trim(),
      year_of_passing: gradingForm.year_of_passing.trim(),
      mode: gradingForm.mode,
      total_marks: gradingForm.mode === "MARKS" ? gradingForm.total_marks.trim() : "",
      obtained_marks: gradingForm.mode === "MARKS" ? gradingForm.obtained_marks.trim() : "",
      entered_percentage: gradingForm.mode === "PERCENT" ? gradingForm.entered_percentage.trim() : "",
      entered_gpa: gradingForm.mode === "GPA" ? gradingForm.entered_gpa.trim() : "",
      declaration_accepted: gradingForm.declaration_accepted,
      preview_confirmed: gradingForm.preview_confirmed,
    };

    try {
      const endpoint = gradingActiveRequest?.can_nurse_edit
        ? "/api/nurses/grading-letter/resubmit"
        : "/api/nurses/grading-letter/submit";
      const res = await api.post<{ success?: boolean; reference?: string; message?: string; error?: string }>(endpoint, payload);
      const successMessage = gradingActiveRequest?.can_nurse_edit
        ? `${res.message || "Grading letter request updated successfully."} Reference: ${res.reference || DASH_VALUE}`
        : `Grading letter request submitted successfully. Reference: ${res.reference || DASH_VALUE}`;
      setGradingFlash(successMessage);
      setGradingForm(createGradingForm());
      await refreshGradingSummary(false);
    } catch (error) {
      setGradingError(normalizeRequestError(error, GRADING_SUBMIT_FALLBACK));
    } finally {
      setGradingSubmitBusy(false);
    }
  }

  async function saveGradingMton() {
    const canonical = normalizeMtonNumber(gradingMtonInput);
    setGradingMtonError("");
    setGradingMtonFlash("");
    if (!isValidMtonNumber(canonical)) {
      setGradingMtonError("Please enter a valid MTON number in this format: MTON-E-145");
      return;
    }
    setGradingMtonBusy(true);
    try {
      const res = await api.post<{
        success?: boolean;
        mton_number?: string;
        message?: string;
        warning?: string;
        error?: string;
      }>("/api/nurses/mton/save", {
        nurse_reference_id: ctx.referenceId,
        session_marker: ctx.sessionMarker || "",
        mton_number: canonical,
      });
      const savedNumber = normalizeMtonNumber(res.mton_number || canonical);
      commitPortalContext((prev) => ({ ...prev, mtonNumber: savedNumber }));
      setGradingMtonInput(savedNumber);
      setGradingMtonFlash([res.message || "MTON number saved.", res.warning || ""].filter(Boolean).join(" "));
      await refreshGradingSummary(false);
    } catch (error) {
      setGradingMtonError(normalizeRequestError(error, GRADING_MTON_FALLBACK));
    } finally {
      setGradingMtonBusy(false);
    }
  }

  async function cancelGradingRequest() {
    if (!gradingActiveRequest?.id) return;
    const confirmed = window.confirm("Cancel this grading letter request? You can submit a fresh request later.");
    if (!confirmed) return;
    setGradingSubmitBusy(true);
    setGradingError("");
    setGradingFlash("");
    try {
      const res = await api.post<{ success?: boolean; message?: string; error?: string }>("/api/nurses/grading-letter/cancel", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        session_marker: ctx.sessionMarker || "",
        id: gradingActiveRequest.id,
      });
      setGradingFlash(res.message || "Grading letter request cancelled.");
      setGradingForm(createGradingForm());
      await refreshGradingSummary(false);
    } catch (error) {
      setGradingError(normalizeRequestError(error, "Request could not be cancelled. Please try again."));
    } finally {
      setGradingSubmitBusy(false);
    }
  }

  async function submitChangePassword() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.post("/api/nurses/change-password", {
        nurse_reference_id: ctx.referenceId,
        current_password: curPwd,
        new_password: newPwd,
        confirm_password: confirmNew,
      });
      setMsg("Password updated.");
      setCurPwd("");
      setNewPwd("");
      setConfirmNew("");
    } catch (e) {
      setErr((e as Error).message || "Could not change password.");
    } finally {
      setBusy(false);
    }
  }

  async function submitProfileUpdate() {
    setProfileSaveBusy(true);
    setProfileError("");
    setProfileFlash("");
    try {
      const email = profileForm.email.trim().toLowerCase();
      const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!email || !re.test(email)) throw new Error("Please enter a valid email address.");
      const mton = normalizeMtonNumber(profileForm.mton_number);
      if (mton && !isValidMtonNumber(mton)) {
        throw new Error("Please enter a valid MTON number in this format: MTON-E-145");
      }
      const res = await api.post<{ success?: boolean; message?: string; warning?: string; profile?: unknown; error?: string }>("/api/nurses/profile/update", {
        nurse_reference_id: ctx.referenceId,
        session_marker: ctx.sessionMarker || "",
        father_name: profileForm.father_name.trim(),
        email,
        primary_mobile: profileForm.primary_mobile.trim(),
        whatsapp: profileForm.whatsapp.trim(),
        civil_id: profileForm.civil_id.trim(),
        cnic: profileForm.cnic.trim(),
        mton_number: mton,
        qualification_degree: profileForm.qualification_degree,
        qualification_degree_other: profileForm.qualification_degree_other.trim(),
        workplace: profileForm.workplace.trim(),
      });
      const updatedProfile = buildPortalContextFromApiData(res.profile || {});
      commitPortalContext((prev) => ({
        ...prev,
        ...updatedProfile,
        sessionMarker: prev.sessionMarker,
      }));
      setQualificationInfo({
        degree: updatedProfile.qualificationDegree || "",
        other: updatedProfile.qualificationDegreeOther || "",
      });
      setCurrentEmail(updatedProfile.email || email);
      setCurrentEmailStatus(updatedProfile.emailStatus || (updatedProfile.email === email && updatedProfile.email ? "Verification Pending" : currentEmailStatus));
      setProfileFlash(res.message || "Profile updated. Embassy may verify changes before using them for official documents.");
      if (res.warning) setProfileError(res.warning);
      setShowProfileEditor(false);
      await refreshGradingSummary(false);
    } catch (e) {
      setProfileError((e as Error).message || "Profile changes could not be saved.");
    } finally {
      setProfileSaveBusy(false);
    }
  }

  async function resendEmailVerification() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      const res = await api.post<{ success?: boolean; message?: string; warning?: string }>(
        "/api/nurses/resend-email-verification",
        { nurse_reference_id: ctx.referenceId, session_marker: ctx.sessionMarker || "" }
      );
      setCurrentEmailStatus("Verification Pending");
      setMsg((res.message || "Verification email sent.") + " Please check your spam/junk folder if you do not see the verification email.");
      if (res.warning) setErr(res.warning);
    } catch (e) {
      setErr((e as Error).message || "Could not resend verification email.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fade-in nurse-portal-page" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <main style={{ flex: 1, maxWidth: 1120, margin: "0 auto", width: "100%", padding: pagePadding, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ fontSize: "clamp(24px, 5vw, 28px)", color: "#2D4A6B", lineHeight: 1.2 }}>
            Welcome, {ctx.fullName || "Nurse"}
          </h1>
          <Btn
            variant="light"
            onClick={() => {
              clearNursePortal();
              navigate("/nurses/login");
            }}
          >
            Logout / Clear Portal Session
          </Btn>
        </div>
        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "nowrap",
            overflowX: "auto",
            WebkitOverflowScrolling: "touch",
            paddingBottom: 4,
            marginBottom: 14,
          }}
        >
          {tabs.map((t) => (
            <Btn
              key={t}
              variant={activeTab === t ? "navy" : "light"}
              onClick={() => setParams({ tab: t })}
              style={{ flex: "0 0 auto" }}
            >
              {t === "overview"
                ? "Overview"
                : t === "stay"
                  ? "Stay Arrangement"
                  : t === "complaint"
                    ? "Complaint"
                    : t === "grading"
                      ? "Grading Letter"
                    : t === "onboarding"
                      ? "MOH Onboarding"
                    : t === "leaving"
                      ? "Leaving Notice"
                      : t === "requests"
                        ? "My Requests"
                        : "Change password"}
            </Btn>
          ))}
        </div>

        {(msg || err) ? (
          <div style={{ marginBottom: 14, background: err ? "#fff4f4" : "#f3fff4", color: err ? "#991b1b" : "#166534", border: `1px solid ${err ? "#fecaca" : "#bbf7d0"}`, borderRadius: 10, padding: 10 }}>
            {err || msg}
          </div>
        ) : null}

        {pendingArrival ? (
          <div style={{ marginBottom: 14 }}>
            <NoticeBox tone="warning">{pendingArrivalBanner}</NoticeBox>
          </div>
        ) : null}

        {activeTab === "overview" ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: overviewGridColumns, gap: 14, marginBottom: 14 }}>
              <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: "clamp(14px, 3vw, 16px)", minWidth: 0 }}>
                <h3 style={{ marginBottom: 10, color: "#2D4A6B" }}>Nurse Profile Summary</h3>
                <div style={{ display: "grid", gridTemplateColumns: detailGridColumns, gap: 10 }}>
                  <Field label="Reference ID" value={ctx.referenceId || "-"} />
                  <Field label="Name" value={ctx.fullName || "-"} />
                  <Field label="Father Name" value={ctx.fatherName || "—"} />
                  <Field label="Email" value={ctx.email || "-"} />
                  <Field label="Primary Mobile" value={ctx.mobileFull || ctx.mobile || "—"} />
                  <Field label="WhatsApp" value={ctx.whatsappFull || ctx.mobileFull || ctx.mobile || "—"} />
                  <Field label="Emergency Contact" value={ctx.emergencyContactFull || "—"} />
                  <Field label="Passport" value={ctx.passportMasked || "-"} />
                  <Field label="Civil ID (if any)" value={ctx.civilIdMasked || "—"} />
                  <Field label="MOH / MTON Number" value={ctx.mtonNumber || "—"} />
                  <Field label="Qualification / Degree" value={qualificationDisplay} />
                  <Field label="Status" value={ctx.registrationStatus || "-"} />
                  <Field label="Last Updated" value={ctx.lastUpdated || "-"} />
                  <Field label="Housing Account" value={housingAccount?.statusLabel || "Active"} />
                  {housingAccount?.batchCode ? (
                    <Field
                      label="Arrival Batch"
                      value={normalizeArrivalBatchNumber(housingAccount.batchCode) || housingAccount.batchCode}
                    />
                  ) : null}
                  {housingAccount?.arrivalDate ? <Field label="Arrival Date" value={housingAccount.arrivalDate} /> : null}
                  {showStaySummary ? <Field label="Current Stay Arrangement" value={currentArrangement} /> : null}
                  {showStaySummary ? <Field label="Latest Monthly Check-in" value={monthlyCheckinStatus || "—"} /> : null}
                  {monthlyCheckinReceivedAt ? <Field label="Check-in Received" value={monthlyCheckinReceivedAt} /> : null}
                  {hasEmbassyArrangement ? <Field label="Approved Vendor / Service Provider" value={approvedVendorLabel.replace("Approved Vendor: ", "")} /> : null}
                  {hasEmbassyArrangement ? <Field label="Facility / Building" value={ctx.facilityRoster?.facility_name || "—"} /> : null}
                  {showStaySummary && stayArea ? <Field label="Area" value={stayArea} /> : null}
                  {hasEmbassyArrangement && ctx.facilityRoster?.date_shifted_to_facility ? (
                    <Field label="Date shifted to facility" value={ctx.facilityRoster.date_shifted_to_facility} />
                  ) : null}
                  {hasEmbassyArrangement && stayReminderPref ? (
                    <Field label="Notice reminders" value={stayReminderPref} />
                  ) : null}
                  {isMohHotel && mohHotelName ? (
                    <Field label="Hotel / Facility" value={mohHotelName} />
                  ) : null}
                  {isMohHotel && mohHotelArea ? (
                    <Field label="Hotel Area" value={mohHotelArea} />
                  ) : null}
                  {isMohHotel && mohHotelStartDate ? (
                    <Field label="Arrival Stay Start" value={mohHotelStartDate} />
                  ) : null}
                  {isMohHotel && mohHotelExpectedEndDate ? (
                    <Field label="Expected End Date" value={mohHotelExpectedEndDate} />
                  ) : null}
                  {isMohHotel ? (
                    <Field label="Expected Duration" value={`${mohHotelDurationMonths} month(s)`} />
                  ) : null}
                </div>
              </div>
              <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: "clamp(14px, 3vw, 16px)", minWidth: 0 }}>
                <h3 style={{ marginBottom: 10, color: "#2D4A6B" }}>Tracking / Status</h3>
                <div style={{ marginBottom: 8 }}><StatusBadge type={statusType as any} label={ctx.registrationStatus || "Pending"} /></div>
                <p style={{ color: "#5B6773", fontSize: 13, marginTop: 8 }}><strong>Embassy remarks:</strong> {ctx.remarks || "No remarks yet."}</p>
                <p style={{ color: "#5B6773", fontSize: 13, marginTop: 8 }}><strong>What you should do now:</strong> Keep tracking this portal for review updates and follow any Embassy remarks.</p>
                {showStaySummary ? (
                  <div style={{ marginTop: 14, borderTop: "1px solid #E3EBF0", paddingTop: 12 }}>
                    <p style={{ color: "#5B6773", fontSize: 13, margin: "0 0 8px" }}>
                      <strong>Monthly welfare check-in:</strong> {monthlyCheckinStatus || "No active monthly check-in."}
                    </p>
                    {monthlyCheckinPending && monthlyCheckinUrl ? (
                      <Btn variant="primary" onClick={() => window.location.assign(monthlyCheckinUrl)}>
                        Complete Monthly Welfare Check-in
                      </Btn>
                    ) : monthlyCheckinReceivedAt ? (
                      <p style={{ color: "#166534", fontSize: 13, margin: 0 }}>
                        Your latest monthly welfare check-in was received on {monthlyCheckinReceivedAt}.
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
            <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: "clamp(14px, 3vw, 16px)", minWidth: 0 }}>
              <h3 style={{ marginBottom: 8, color: "#2D4A6B" }}>Embassy Messages</h3>
              <p style={{ color: "#5B6773" }}>{ctx.remarks || "Embassy messages and remarks will appear here after review."}</p>
            </div>
            <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: "clamp(14px, 3vw, 16px)", marginTop: 14, minWidth: 0 }}>
              <h3 style={{ marginBottom: 8, color: "#2D4A6B" }}>Profile & Contact Details</h3>
              <p style={{ fontSize: 13, color: "#5B6773", lineHeight: 1.6 }}>
                You can update your current biodata here for future Embassy review. Name and passport number stay read-only to avoid identity mismatch.
              </p>
              {profileFlash ? <NoticeBox tone="success">{profileFlash}</NoticeBox> : null}
              {profileError ? <NoticeBox tone="error">{profileError}</NoticeBox> : null}
              <div style={{ display: "grid", gridTemplateColumns: detailGridColumns, gap: 10, marginTop: 10 }}>
                <Field label="Read-only Name" value={ctx.fullName || "—"} />
                <Field label="Read-only Passport" value={ctx.passportMasked || "—"} />
                <Field label="Current Email" value={currentEmail || "—"} />
                <Field label="Email Status" value={emailStatusText} />
                <Field label="Current Qualification" value={qualificationDisplay} />
                <Field label="Current Workplace / Hospital" value={ctx.hospital || "—"} />
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                <Btn variant="light" onClick={() => { setShowProfileEditor((s) => !s); setProfileError(""); setProfileFlash(""); }}>
                  {showProfileEditor ? "Close Profile Editor" : "Edit Profile"}
                </Btn>
                {(emailStatus || "").toLowerCase() !== "verified" ? (
                  <Btn variant="light" onClick={resendEmailVerification} disabled={busy}>Resend Verification Email</Btn>
                ) : null}
              </div>
              {showProfileEditor ? (
                <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
                  <div style={{ display: "grid", gridTemplateColumns: detailGridColumns, gap: 10 }}>
                    <label>Father Name<input className="f-input" value={profileForm.father_name} onChange={(e) => setProfileForm({ ...profileForm, father_name: e.target.value })} /></label>
                    <label>Email<input className="f-input" type="email" value={profileForm.email} onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })} /></label>
                    <label>Primary Mobile<input className="f-input" value={profileForm.primary_mobile} onChange={(e) => setProfileForm({ ...profileForm, primary_mobile: e.target.value })} /></label>
                    <label>WhatsApp<input className="f-input" value={profileForm.whatsapp} onChange={(e) => setProfileForm({ ...profileForm, whatsapp: e.target.value })} /></label>
                    <label>Civil ID<input className="f-input" value={profileForm.civil_id} onChange={(e) => setProfileForm({ ...profileForm, civil_id: e.target.value })} /></label>
                    <label>CNIC<input className="f-input" value={profileForm.cnic} onChange={(e) => setProfileForm({ ...profileForm, cnic: e.target.value })} /></label>
                    <label>MOH / MTON Number<input className="f-input" placeholder="MTON-E-145" value={profileForm.mton_number} onChange={(e) => setProfileForm({ ...profileForm, mton_number: e.target.value })} /></label>
                    <label>
                      Qualification / Degree
                      <select className="f-input" value={profileForm.qualification_degree} onChange={(e) => setProfileForm({ ...profileForm, qualification_degree: e.target.value })}>
                        <option value="">Select</option>
                        {PROFILE_QUALIFICATION_OPTIONS.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>
                    {profileForm.qualification_degree === "Other" ? (
                      <label>Other Qualification / Degree<input className="f-input" value={profileForm.qualification_degree_other} onChange={(e) => setProfileForm({ ...profileForm, qualification_degree_other: e.target.value })} /></label>
                    ) : null}
                    <label>Current Workplace / Hospital<input className="f-input" value={profileForm.workplace} onChange={(e) => setProfileForm({ ...profileForm, workplace: e.target.value })} /></label>
                  </div>
                  <Btn variant="primary" onClick={submitProfileUpdate} disabled={profileSaveBusy}>
                    {profileSaveBusy ? "Saving..." : "Save Changes"}
                  </Btn>
                </div>
              ) : null}
            </div>
          </>
        ) : null}

        {activeTab === "stay" ? (
          stayAccessBlocked ? (
            <PendingArrivalPanel title="Stay Arrangement" message={stayBlockedMessage} />
          ) : (
          <div style={{ display: "grid", gap: 14 }}>
            {ctx.facilityRoster && !isDoctor ? (
              <FormCard title="Stay Arrangement Confirmation">
                <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                  {hasEmbassyArrangement ? stayArrangementText : "Our records show that you may be linked to an Embassy-facilitated stay arrangement through an approved service provider."}
                  {" "}Please confirm your current stay details so the Community Welfare Wing can maintain accurate welfare records and provide
                  timely support where required.
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
                  <Field label="Roster Reference" value={ctx.facilityRoster.roster_reference || "-"} />
                  <Field label="Facility / Building" value={ctx.facilityRoster.facility_name || "-"} />
                  {hasEmbassyArrangement ? <Field label="Approved Vendor" value={approvedVendorLabel.replace("Approved Vendor: ", "")} /> : null}
                  <Field label="Monthly Check-in Status" value={monthlyCheckinStatus || "—"} />
                  <Field label="Last Check-in Response" value={monthlyCheckinReceivedAt || "—"} />
                  <Field label="Notice Period Start" value={ctx.facilityRoster.notice_period_start_date || "-"} />
                </div>
                {monthlyCheckinPending && monthlyCheckinUrl ? (
                  <Btn variant="primary" onClick={() => window.location.assign(monthlyCheckinUrl)}>
                    Complete Monthly Welfare Check-in
                  </Btn>
                ) : null}
                <label>
                  Confirmation option
                  <select className="f-input" value={stay.confirmation_option} onChange={(e) => setStay({ ...stay, confirmation_option: e.target.value })}>
                    <option value="">Select</option>
                    <option value="currently_staying">I am currently staying at this facility</option>
                    <option value="shifted_from_facility">I have shifted from this facility</option>
                    <option value="intends_to_leave">I intend to leave/change my stay arrangement</option>
                    <option value="details_correction">My facility details require correction</option>
                    <option value="assistance_requested">I need welfare assistance/follow-up</option>
                  </select>
                </label>
                <label>Current facility name<input className="f-input" value={stay.current_facility_name} onChange={(e) => setStay({ ...stay, current_facility_name: e.target.value })} /></label>
                <label>Area<input className="f-input" value={stay.area} onChange={(e) => setStay({ ...stay, area: e.target.value })} /></label>
                <div style={{ display: "grid", gridTemplateColumns: compactGridColumns, gap: 10 }}>
                  <label>Room<input className="f-input" value={stay.room_number} onChange={(e) => setStay({ ...stay, room_number: e.target.value })} /></label>
                  <label>Bed<input className="f-input" value={stay.bed_number} onChange={(e) => setStay({ ...stay, bed_number: e.target.value })} /></label>
                </div>
                <label>Current phone / WhatsApp<input className="f-input" value={stay.current_phone} onChange={(e) => setStay({ ...stay, current_phone: e.target.value })} /></label>
                <label>
                  Preferred contact method
                  <select className="f-input" value={stay.preferred_contact_method} onChange={(e) => setStay({ ...stay, preferred_contact_method: e.target.value })}>
                    <option>WhatsApp</option>
                    <option>Phone Call</option>
                    <option>Email</option>
                  </select>
                </label>
                <label>Remarks<textarea className="f-input" value={stay.remarks} onChange={(e) => setStay({ ...stay, remarks: e.target.value })} /></label>
                <Btn variant="primary" disabled={busy || !stay.confirmation_option} onClick={submitStayConfirmation}>{busy ? "Submitting..." : "Submit Stay Confirmation"}</Btn>
              </FormCard>
            ) : (
              <FormCard title="Stay Arrangement Confirmation">
                <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                  No Embassy-facilitated facility record is currently linked to your profile.
                  You may still submit a facility assistance request if you need Community Welfare Wing follow-up.
                </p>
              </FormCard>
            )}
            <FormCard title="Facility Assistance Request">
              <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                Please share any welfare-related service difficulty or request for assistance regarding your current stay arrangement.
                The Community Welfare Wing will review the request and may contact you for follow-up.
              </p>
              <label>
                Category
                <select className="f-input" value={facilityReq.category} onChange={(e) => setFacilityReq({ ...facilityReq, category: e.target.value })}>
                  <option value="">Select</option>
                  <option>General welfare assistance</option>
                  <option>Basic services concern</option>
                  <option>Facility maintenance concern</option>
                  <option>Shared space concern</option>
                  <option>Safety or security concern</option>
                  <option>Cleanliness / hygiene concern</option>
                  <option>Communication / coordination concern</option>
                  <option>Transport-related concern</option>
                  <option>Request for meeting or callback</option>
                  <option>Request to change stay arrangement</option>
                  <option>Other</option>
                </select>
              </label>
              <label>
                Urgency
                <select className="f-input" value={facilityReq.urgency} onChange={(e) => setFacilityReq({ ...facilityReq, urgency: e.target.value })}>
                  <option>Normal</option>
                  <option>Priority</option>
                  <option>Urgent</option>
                </select>
              </label>
              <label>Subject<input className="f-input" value={facilityReq.subject} onChange={(e) => setFacilityReq({ ...facilityReq, subject: e.target.value })} /></label>
              <label>Details<textarea className="f-input" value={facilityReq.details} onChange={(e) => setFacilityReq({ ...facilityReq, details: e.target.value })} /></label>
              <label>
                Preferred contact method
                <select className="f-input" value={facilityReq.preferred_contact_method} onChange={(e) => setFacilityReq({ ...facilityReq, preferred_contact_method: e.target.value })}>
                  <option>WhatsApp</option>
                  <option>Phone Call</option>
                  <option>Email</option>
                </select>
              </label>
              <Btn variant="primary" disabled={busy || !facilityReq.category || !facilityReq.details} onClick={submitFacilityRequest}>{busy ? "Submitting..." : "Submit Facility Assistance Request"}</Btn>
            </FormCard>
          </div>
          )
        ) : null}

        {activeTab === "complaint" ? (
          complaintAccessBlocked ? (
            <PendingArrivalPanel title="Complaint / Welfare Issue" message={complaintBlockedMessage} />
          ) : (
            <FormCard title="Complaint / Welfare Issue">
              <label>Category<input className="f-input" value={complaint.complaint_category} onChange={(e) => setComplaint({ ...complaint, complaint_category: e.target.value })} /></label>
              <label>Priority<select className="f-input" value={complaint.priority} onChange={(e) => setComplaint({ ...complaint, priority: e.target.value })}><option>Normal</option><option>Important</option><option>Urgent</option></select></label>
              <label>Subject<input className="f-input" value={complaint.subject} onChange={(e) => setComplaint({ ...complaint, subject: e.target.value })} /></label>
              <label>Details<textarea className="f-input" value={complaint.description} onChange={(e) => setComplaint({ ...complaint, description: e.target.value })} /></label>
              <Btn variant="primary" disabled={busy} onClick={submitComplaint}>{busy ? "Submitting..." : "Submit Complaint"}</Btn>
            </FormCard>
          )
        ) : null}

        {activeTab === "grading" ? (
          gradingAccessBlocked ? (
            <PendingArrivalPanel title="Grading Letter Request" message={gradingBlockedMessage} />
          ) : (
          <div style={{ display: "grid", gap: 14 }}>
            <style>{`@media print {.grading-preview-print-hide{display:none!important}.grading-preview-shell{display:none!important}}`}</style>
            <FormCard title="Grading Letter Request">
              <NoticeBox>
                Use this form to request an Embassy grading letter for one nursing qualification. One qualification
                requires one application. Midwifery or additional qualification should be submitted as a separate
                request.
              </NoticeBox>
              <NoticeBox tone="warning">
                Submitting this form does not generate the official letter automatically. Embassy/Nurses Desk will
                verify the details before issuing the final letter.
              </NoticeBox>
              <NoticeBox tone="info">
                Please bring original degree/transcript/marksheet for verification when requested by Embassy.
              </NoticeBox>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
                <Field label="Name" value={displayValue(gradingProfile.full_name || ctx.fullName)} />
                <Field label="Father Name" value={displayValue(gradingProfile.father_name || ctx.fatherName)} />
                <Field label="Passport No." value={displayValue(gradingProfile.passport_number || ctx.passportNumber)} />
                <Field label="CNIC" value={displayValue(gradingProfile.cnic)} />
                <Field label="Mobile" value={displayValue(gradingProfile.mobile || ctx.mobileFull || ctx.mobile)} />
                <Field label="Email" value={displayValue(gradingProfile.email || currentEmail)} />
                <Field label="MOH / MTON Number" value={displayValue(savedMtonNumber)} />
              </div>

              {gradingFlash ? <NoticeBox tone="success">{gradingFlash}</NoticeBox> : null}
              {gradingError ? <NoticeBox tone="error">{gradingError}</NoticeBox> : null}
              {gradingMtonFlash ? <NoticeBox tone="success">{gradingMtonFlash}</NoticeBox> : null}
              {gradingMtonError ? <NoticeBox tone="error">{gradingMtonError}</NoticeBox> : null}

              {gradingLoading ? (
                <p style={{ color: "#5B6773", margin: 0 }}>Loading grading letter details...</p>
              ) : null}

              {!gradingLoading && gradingActiveRequest ? (
                <div
                  style={{
                    border: "1px solid #E3EBF0",
                    borderRadius: 10,
                    padding: 14,
                    background: "#F7FAFC",
                    display: "grid",
                    gap: 8,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                    <strong>{gradingActiveRequest.ref_no || gradingActiveRequest.reference || "Active Request"}</strong>
                    <StatusBadge
                      type={gradingStatusType(gradingActiveRequest.status || "") as any}
                      label={prettifyGradingStatus(gradingActiveRequest.status || "SUBMITTED")}
                    />
                  </div>
                  <p style={{ margin: 0, color: "#5B6773", fontSize: 13 }}>
                    Qualification:{" "}
                    {qualificationLabelFromCode(
                      gradingActiveRequest.qualification_code || "",
                      gradingActiveRequest.qualification_other || ""
                    )}
                  </p>
                  <p style={{ margin: 0, color: "#5B6773", fontSize: 13 }}>
                    {normalizeGradingIdentifierType(
                      gradingActiveRequest.student_identifier_type || gradingActiveRequest.student_no_label || ""
                    )}
                    : {gradingActiveRequest.student_no || DASH_VALUE}
                  </p>
                  <p style={{ margin: 0, color: "#5B6773", fontSize: 13 }}>
                    Submitted date: {gradingActiveRequest.submitted_at || gradingActiveRequest.created_at || DASH_VALUE}
                  </p>
                  {gradingActiveRequest.correction_notes ? (
                    <p style={{ margin: 0, color: "#8A5C00", fontSize: 13 }}>
                      Correction notes: {gradingActiveRequest.correction_notes}
                    </p>
                  ) : null}
                  {gradingActiveRequest.can_nurse_edit ? (
                    <p style={{ margin: 0, color: "#2D4A6B", fontSize: 13 }}>
                      {(gradingActiveRequest.status || "").toUpperCase() === "CORRECTION_REQUIRED"
                        ? "Please correct the request details below, review the preview again, and resubmit."
                        : "You can still update this submitted request until Embassy review begins."}
                    </p>
                  ) : (
                    <p style={{ margin: 0, color: "#5B6773", fontSize: 13 }}>
                      You already have an active grading letter request. You can submit a new request after the current
                      one is issued, rejected, or cancelled.
                    </p>
                  )}
                  {gradingActiveRequest.can_nurse_cancel ? (
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <Btn variant="light" onClick={cancelGradingRequest} disabled={gradingSubmitBusy}>
                        Cancel Current Request
                      </Btn>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {!hasSavedMtonNumber ? (
                <div
                  style={{
                    border: "1px solid #E3EBF0",
                    borderRadius: 10,
                    padding: 14,
                    background: "#F7FAFC",
                    display: "grid",
                    gap: 10,
                  }}
                >
                  <div>
                    <h4 style={{ margin: "0 0 6px", color: "#2D4A6B" }}>Enter MOH / MTON Number</h4>
                    <p style={{ margin: 0, color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                      Please enter your MOH / MTON number issued for your Ministry of Health arrival process. This
                      number is required before submitting a grading letter request.
                    </p>
                  </div>
                  <label>
                    MOH / MTON Number
                    <input
                      className="f-input"
                      placeholder="MTON-E-145"
                      value={gradingMtonInput}
                      onChange={(e) => setGradingMtonInput(e.target.value)}
                    />
                  </label>
                  <p style={{ margin: 0, color: "#5B6773", fontSize: 13 }}>
                    Enter the number exactly in this format: MTON-E-145
                  </p>
                  <Btn variant="primary" disabled={gradingMtonBusy} onClick={saveGradingMton}>
                    {gradingMtonBusy ? "Saving..." : "Continue to Grading Letter Form"}
                  </Btn>
                </div>
              ) : null}

              {hasSavedMtonNumber && !gradingLoading && !gradingError && (!gradingActiveRequest || gradingActiveRequest.can_nurse_edit) ? (
                <>
                  <label>
                    Qualification Type
                    <select
                      className="f-input"
                      value={gradingForm.qualification_code}
                      onChange={(e) => setGradingForm({ ...gradingForm, qualification_code: e.target.value })}
                    >
                      <option value="">Select</option>
                      {GRADING_QUALIFICATIONS.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Degree Title as printed on certificate
                    <input
                      className="f-input"
                      value={gradingForm.degree_title}
                      onChange={(e) => setGradingForm({ ...gradingForm, degree_title: e.target.value })}
                    />
                  </label>
                  <label>
                    Identifier Type
                    <select
                      className="f-input"
                      value={gradingForm.student_identifier_type}
                      onChange={(e) =>
                        setGradingForm({
                          ...gradingForm,
                          student_identifier_type: normalizeGradingIdentifierType(e.target.value),
                        })
                      }
                    >
                      {GRADING_IDENTIFIER_TYPES.map((label) => (
                        <option key={label} value={label}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Identifier Value
                    <input
                      className="f-input"
                      placeholder="Enter the number exactly as printed on your certificate/transcript."
                      value={gradingForm.student_no}
                      onChange={(e) => setGradingForm({ ...gradingForm, student_no: e.target.value })}
                    />
                  </label>
                  <label>
                    College / Institute
                    <input
                      className="f-input"
                      value={gradingForm.institute}
                      onChange={(e) => setGradingForm({ ...gradingForm, institute: e.target.value })}
                    />
                  </label>
                  <label>
                    University / Affiliating Body
                    <input
                      className="f-input"
                      value={gradingForm.university}
                      onChange={(e) => setGradingForm({ ...gradingForm, university: e.target.value })}
                    />
                  </label>
                  <label>
                    Year of Passing
                    <input
                      className="f-input"
                      type="number"
                      min="1950"
                      max={new Date().getFullYear() + 1}
                      value={gradingForm.year_of_passing}
                      onChange={(e) => setGradingForm({ ...gradingForm, year_of_passing: e.target.value })}
                    />
                  </label>

                  <label>
                    Grading Mode
                    <select
                      className="f-input"
                      value={gradingForm.mode}
                      onChange={(e) =>
                        setGradingForm({
                          ...gradingForm,
                          mode: e.target.value as GradingMode,
                          total_marks: e.target.value === "MARKS" ? gradingForm.total_marks : "",
                          obtained_marks: e.target.value === "MARKS" ? gradingForm.obtained_marks : "",
                          entered_percentage: e.target.value === "PERCENT" ? gradingForm.entered_percentage : "",
                          entered_gpa: e.target.value === "GPA" ? gradingForm.entered_gpa : "",
                        })
                      }
                    >
                      <option value="MARKS">Marks</option>
                      <option value="PERCENT">Percentage</option>
                      <option value="GPA">GPA out of 4.00</option>
                    </select>
                  </label>

                  {gradingForm.mode === "MARKS" ? (
                    <div style={{ display: "grid", gridTemplateColumns: compactGridColumns, gap: 10 }}>
                      <label>
                        Total Marks
                        <input
                          className="f-input"
                          type="number"
                          min="0"
                          step="0.01"
                          value={gradingForm.total_marks}
                          onChange={(e) => setGradingForm({ ...gradingForm, total_marks: e.target.value })}
                        />
                      </label>
                      <label>
                        Obtained Marks
                        <input
                          className="f-input"
                          type="number"
                          min="0"
                          step="0.01"
                          value={gradingForm.obtained_marks}
                          onChange={(e) => setGradingForm({ ...gradingForm, obtained_marks: e.target.value })}
                        />
                      </label>
                    </div>
                  ) : null}

                  {gradingForm.mode === "PERCENT" ? (
                    <label>
                      Percentage
                      <input
                        className="f-input"
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={gradingForm.entered_percentage}
                        onChange={(e) => setGradingForm({ ...gradingForm, entered_percentage: e.target.value })}
                      />
                    </label>
                  ) : null}

                  {gradingForm.mode === "GPA" ? (
                    <div style={{ display: "grid", gap: 8 }}>
                      <label>
                        GPA Obtained
                        <input
                          className="f-input"
                          type="number"
                          min="0"
                          max="4"
                          step="0.01"
                          value={gradingForm.entered_gpa}
                          onChange={(e) => setGradingForm({ ...gradingForm, entered_gpa: e.target.value })}
                        />
                      </label>
                      <p style={{ margin: 0, color: "#5B6773", fontSize: 13 }}>Maximum GPA: 4.00</p>
                    </div>
                  ) : null}

                  <div
                    style={{
                      border: "1px solid #E3EBF0",
                      borderRadius: 10,
                      padding: 14,
                      background: "#F7FAFC",
                      display: "grid",
                      gap: 6,
                    }}
                  >
                    <div style={{ color: "#2D4A6B", fontWeight: 700 }}>Computed Percentage</div>
                    <div style={{ fontSize: 18, fontWeight: 800, color: "#1F2933" }}>
                      {gradingPreview.percentage != null ? `${gradingPreview.percentage.toFixed(2)}%` : DASH_VALUE}
                    </div>
                    <div style={{ color: "#2D4A6B", fontWeight: 700 }}>Provisional Grade Label</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "#1F2933" }}>{gradingPreview.gradeLabel}</div>
                    <p style={{ margin: 0, color: "#5B6773", fontSize: 13 }}>
                      Final grade is verified by Embassy/Nurses Desk before letter is issued.
                    </p>
                    {gradingPreview.validationMessage ? (
                      <p style={{ margin: 0, color: "#C0392B", fontSize: 13 }}>{gradingPreview.validationMessage}</p>
                    ) : null}
                  </div>

                  <div className="grading-preview-print-hide" style={{ display: "grid", gap: 10 }}>
                    <div style={{ fontSize: 20, fontWeight: 800, color: "#2D4A6B" }}>Preview for Checking Only</div>
                    <NoticeBox tone="warning">
                      This preview is only for checking spelling and data before submission. It is not an official Embassy
                      letter and cannot be used for any official purpose. The Embassy/Nurses Desk will verify the details
                      before issuing the final letter.
                    </NoticeBox>
                    <OfficialLetterPreview ctx={ctx} profile={gradingProfile} form={gradingForm} computed={gradingPreview} />
                  </div>

                  <label style={{ display: "flex", gap: 8, alignItems: "flex-start", color: "#334155" }}>
                    <input
                      type="checkbox"
                      checked={gradingForm.preview_confirmed}
                      onChange={(e) =>
                        setGradingForm({ ...gradingForm, preview_confirmed: e.target.checked })
                      }
                      style={{ marginTop: 3 }}
                    />
                    <span>
                      I have reviewed the preview and confirm the information is correct to the best of my knowledge.
                    </span>
                  </label>

                  <label style={{ display: "flex", gap: 8, alignItems: "flex-start", color: "#334155" }}>
                    <input
                      type="checkbox"
                      checked={gradingForm.declaration_accepted}
                      onChange={(e) =>
                        setGradingForm({ ...gradingForm, declaration_accepted: e.target.checked })
                      }
                      style={{ marginTop: 3 }}
                    />
                    <span>
                      I confirm the information is true and based on my documents. I understand the Embassy issues
                      this letter on request without liability.
                    </span>
                  </label>

                  <Btn variant="primary" disabled={gradingSubmitBusy || !gradingPreview.canSubmit} onClick={submitGradingLetter}>
                    {gradingSubmitBusy ? "Submitting..." : gradingSubmitLabel}
                  </Btn>
                </>
              ) : null}
            </FormCard>

            <FormCard title="Grading Letter History">
              {gradingLoading ? (
                <p style={{ color: "#5B6773", margin: 0 }}>Loading grading letter details...</p>
              ) : gradingHistory.length ? (
                <div style={{ display: "grid", gap: 8 }}>
                  {gradingHistory.map((item, index) => (
                    <div key={`${item.id || item.ref_no || "gl"}-${index}`} style={{ border: "1px solid #E3EBF0", borderRadius: 10, padding: 12 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                        <strong>{item.ref_no || item.reference || "Grading Letter Request"}</strong>
                        <StatusBadge
                          type={gradingStatusType(item.status || "") as any}
                          label={prettifyGradingStatus(item.status || "SUBMITTED")}
                        />
                      </div>
                      <p style={{ fontSize: 12, color: "#5B6773", margin: "8px 0 4px" }}>
                        Qualification: {qualificationLabelFromCode(item.qualification_code || "", item.qualification_other || "")}
                      </p>
                      <p style={{ fontSize: 12, color: "#5B6773", margin: 0 }}>
                        {normalizeGradingIdentifierType(item.student_identifier_type || item.student_no_label || "")}:{" "}
                        {item.student_no || DASH_VALUE}
                      </p>
                      <p style={{ fontSize: 12, color: "#5B6773", margin: 0 }}>
                        Final %: {formatGradingPercent(item.final_percentage)} | Grade: {item.final_grade_label || DASH_VALUE}
                      </p>
                      <p style={{ fontSize: 12, color: "#5B6773", margin: "4px 0 0" }}>
                        Submitted: {item.submitted_at || item.created_at || DASH_VALUE}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color: "#5B6773", margin: 0 }}>No previous grading letter requests found.</p>
              )}
            </FormCard>
          </div>
          )
        ) : null}

        {activeTab === "onboarding" ? (
          pendingArrival ? (
            <PendingArrivalPanel title="MOH Onboarding Tracker" message={complaintBlockedMessage} />
          ) : (
            <div style={{ display: "grid", gap: 14 }}>
              <FormCard title="MOH Onboarding Tracker">
                <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6, marginTop: 0 }}>
                  Please select your current stage so the Embassy Nurses Welfare Desk can guide and assist you if you are stuck.
                </p>

                {onboardingError ? (
                  <div style={{ marginBottom: 10, background: "#fff4f4", color: "#991b1b", border: "1px solid #fecaca", borderRadius: 10, padding: 10, fontSize: 13 }}>
                    {onboardingError}
                  </div>
                ) : null}
                {onboardingFlash ? (
                  <div style={{ marginBottom: 10, background: "#f3fff4", color: "#166534", border: "1px solid #bbf7d0", borderRadius: 10, padding: 10, fontSize: 13 }}>
                    {onboardingFlash}
                  </div>
                ) : null}

                {onboardingLoading ? (
                  <p style={{ color: "#5B6773", margin: 0 }}>Loading onboarding status...</p>
                ) : (
                  <>
                    <label>
                      Current Stage
                      <select
                        className="f-input"
                        value={onboardingForm.current_stage_code}
                        onChange={(e) => setOnboardingForm({ ...onboardingForm, current_stage_code: e.target.value })}
                      >
                        <option value="">Select your current stage</option>
                        {(onboardingSummary?.steps || []).map((s) => (
                          <option key={s.step_code} value={s.step_code}>
                            {(s.sort_order || 0)}. {s.step_name}
                          </option>
                        ))}
                      </select>
                    </label>

                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: 13, color: "#334155", marginBottom: 6 }}>Issue status</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        {[
                          { value: "NO_ISSUE", label: "No issue" },
                          { value: "WAITING", label: "Waiting / pending" },
                          { value: "NEED_HELP", label: "Need Embassy help" },
                        ].map((opt) => (
                          <label
                            key={opt.value}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                              padding: "6px 10px",
                              border: `1px solid ${onboardingForm.issue_status === opt.value ? "#2D4A6B" : "#E3EBF0"}`,
                              background: onboardingForm.issue_status === opt.value ? "#EEF4FB" : "#fff",
                              borderRadius: 999,
                              cursor: "pointer",
                              fontSize: 13,
                              color: "#1f2937",
                            }}
                          >
                            <input
                              type="radio"
                              name="onboarding-issue-status"
                              value={opt.value}
                              checked={onboardingForm.issue_status === opt.value}
                              onChange={(e) => setOnboardingForm({ ...onboardingForm, issue_status: e.target.value })}
                              style={{ margin: 0 }}
                            />
                            {opt.label}
                          </label>
                        ))}
                      </div>
                    </div>

                    <label style={{ marginTop: 10 }}>
                      Optional note
                      <textarea
                        className="f-input"
                        rows={3}
                        placeholder="Optional: briefly explain if you are waiting or need help."
                        value={onboardingForm.nurse_note}
                        onChange={(e) => setOnboardingForm({ ...onboardingForm, nurse_note: e.target.value })}
                      />
                    </label>

                    <Btn variant="primary" disabled={onboardingBusy} onClick={submitOnboardingUpdate}>
                      {onboardingBusy ? "Updating..." : "Update"}
                    </Btn>
                  </>
                )}
              </FormCard>

              <FormCard title="Your Progress">
                {onboardingSummary?.progress?.has_row ? (
                  <>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10, marginBottom: 12 }}>
                      <Field
                        label="Progress"
                        value={`${onboardingSummary.progress?.completed_steps_count || 0} of ${onboardingSummary.progress?.total_steps_count || 17} steps completed (${(onboardingSummary.progress?.progress_percent || 0).toFixed(0)}%)`}
                      />
                      <Field
                        label="Current stage"
                        value={onboardingSummary.progress?.current_step_name || DASH_VALUE}
                      />
                      <Field
                        label="Next step"
                        value={onboardingSummary.progress?.next_step_name || (onboardingSummary.progress?.completed_steps_count === onboardingSummary.progress?.total_steps_count ? "All steps completed" : DASH_VALUE)}
                      />
                      <Field
                        label="Last updated"
                        value={onboardingSummary.progress?.last_updated_at || DASH_VALUE}
                      />
                    </div>

                    {onboardingSummary.progress?.next_step_guidance ? (
                      <div style={{ background: "#F7FAFC", border: "1px solid #E3EBF0", borderRadius: 10, padding: 12, marginTop: 4 }}>
                        <div style={{ fontSize: 12, color: "#5B6773", marginBottom: 4 }}>What happens next</div>
                        <div style={{ color: "#2D4A6B", fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
                          {onboardingSummary.progress?.next_step_name || ""}
                        </div>
                        <div style={{ color: "#1f2937", fontSize: 13, lineHeight: 1.6 }}>
                          {onboardingSummary.progress?.next_step_guidance}
                        </div>
                      </div>
                    ) : null}

                    {onboardingSummary.open_help_request ? (
                      <div style={{ marginTop: 12, background: "#FEF3C7", border: "1px solid #FDE68A", borderRadius: 10, padding: 12 }}>
                        <div style={{ color: "#92400E", fontWeight: 600, marginBottom: 4, fontSize: 14 }}>
                          Help request status: {prettifyOnboardingHelpStatus(onboardingSummary.open_help_request.status || "NEW")}
                        </div>
                        <div style={{ color: "#92400E", fontSize: 13, lineHeight: 1.6 }}>
                          Your request for help has been recorded. The Nurses Welfare Desk may contact you for follow-up.
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p style={{ color: "#5B6773", margin: 0 }}>No status saved yet. Select your current stage and click Update.</p>
                )}
              </FormCard>
            </div>
          )
        ) : null}

        {activeTab === "leaving" ? (
          leavingAccessBlocked ? (
            <PendingArrivalPanel title="Leaving Notice / Change of Stay Arrangement" message={leavingBlockedMessage} />
          ) : (
            <FormCard title="Leaving Notice / Change of Stay Arrangement">
              <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                If you intend to leave or change your current stay arrangement, please submit a Leaving Notice through this portal so that your record can be reviewed and updated in time.
              </p>
              {ctx.facilityRoster?.notice_period_start_date ? (
                <p style={{ color: "#2D4A6B", fontSize: 13, lineHeight: 1.6, background: "#F7FAFC", border: "1px solid #E3EBF0", borderRadius: 10, padding: 10 }}>
                  Based on the dates recorded, your notice period start date is {ctx.facilityRoster.notice_period_start_date}. If you intend to leave or change your stay arrangement, please submit your notice before the applicable deadline where possible.
                </p>
              ) : null}
              <label>Current Facility / Building<input className="f-input" value={leaving.current_facility} onChange={(e) => setLeaving({ ...leaving, current_facility: e.target.value })} /></label>
              <label>Date shifted to facility<input className="f-input" type="date" value={leaving.date_shifted_to_facility} onChange={(e) => setLeaving({ ...leaving, date_shifted_to_facility: e.target.value })} /></label>
              <label>Intended leaving date<input className="f-input" type="date" value={leaving.intended_leaving_date} onChange={(e) => setLeaving({ ...leaving, intended_leaving_date: e.target.value })} /></label>
              <label>
                Reason / category
                <select className="f-input" value={leaving.reason_category} onChange={(e) => setLeaving({ ...leaving, reason_category: e.target.value })}>
                  <option value="">Select</option>
                  <option>Change of stay arrangement</option>
                  <option>Shifted to private option</option>
                  <option>Shifted to family / relative</option>
                  <option>Workplace-arranged option</option>
                  <option>Facility details require correction</option>
                  <option>Other</option>
                </select>
              </label>
              <label>New stay arrangement if known<input className="f-input" value={leaving.new_stay_arrangement} onChange={(e) => setLeaving({ ...leaving, new_stay_arrangement: e.target.value })} /></label>
              <label>New area if known<input className="f-input" value={leaving.new_area} onChange={(e) => setLeaving({ ...leaving, new_area: e.target.value })} /></label>
              <label>
                Do you require assistance in identifying alternative options?
                <select className="f-input" value={leaving.assistance_required} onChange={(e) => setLeaving({ ...leaving, assistance_required: e.target.value })}>
                  <option>No</option>
                  <option>Yes</option>
                </select>
              </label>
              <label>Remarks<textarea className="f-input" value={leaving.remarks} onChange={(e) => setLeaving({ ...leaving, remarks: e.target.value })} /></label>
              <Btn variant="primary" disabled={busy} onClick={submitLeavingNotice}>{busy ? "Submitting..." : "Submit Leaving Notice"}</Btn>
            </FormCard>
          )
        ) : null}

        {activeTab === "password" ? (
            <FormCard title="Change password">
            <label>
              Current password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={curPwd}
                onChange={(e) => setCurPwd(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            <label>
              New password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <label>
              Confirm new password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={confirmNew}
                onChange={(e) => setConfirmNew(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <button
              type="button"
              className="f-input"
              style={{ width: "100%", cursor: "pointer", maxWidth: 220 }}
              onClick={() => setShowPw((s) => !s)}
            >
              {showPw ? "Hide passwords" : "Show passwords"}
            </button>
            <Btn variant="primary" disabled={busy} onClick={submitChangePassword}>
              {busy ? "Updating…" : "Update password"}
            </Btn>
          </FormCard>
        ) : null}

        {activeTab === "requests" ? (
          <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16, marginBottom: 14 }}>
            <h3 style={{ marginBottom: 12, color: "#2D4A6B" }}>My Requests / History</h3>
            {ctx.complaints?.length ? (
              <div style={{ display: "grid", gap: 8, marginBottom: 10 }}>
                {ctx.complaints.slice(0, 10).map((c, idx) => (
                  <div key={c.complaint_id || idx} style={{ border: "1px solid #E3EBF0", borderRadius: 10, padding: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <strong>{c.subject || "Complaint"} {c.complaint_id ? `(${c.complaint_id})` : ""}</strong>
                      <StatusBadge type={(c.status || "").toLowerCase().includes("resolved") ? "resolved" : "processing"} label={c.status || "In Review"} />
                    </div>
                    <p style={{ fontSize: 12, color: "#5B6773" }}>Type: {c.category || "-"} | Submitted: {c.submitted_date || "-"} | Latest update: {c.last_update_date || "-"}</p>
                  </div>
                ))}
              </div>
            ) : null}
            {gradingHistory.length ? (
              <div style={{ display: "grid", gap: 8, marginBottom: 10 }}>
                {gradingHistory.map((item, index) => (
                  <div key={`req-${item.id || item.ref_no || "gl"}-${index}`} style={{ border: "1px solid #E3EBF0", borderRadius: 10, padding: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <strong>{item.ref_no || item.reference || "Grading Letter Request"}</strong>
                      <StatusBadge
                        type={gradingStatusType(item.status || "") as any}
                        label={prettifyGradingStatus(item.status || "SUBMITTED")}
                      />
                    </div>
                    <p style={{ fontSize: 12, color: "#5B6773", margin: "8px 0 0" }}>
                      Qualification: {qualificationLabelFromCode(item.qualification_code || "", item.qualification_other || "")}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}
            {requests.length ? (
              <div style={{ display: "grid", gap: 8 }}>
                {requests.map((r) => (
                  <div key={r.id} style={{ border: "1px dashed #D8E0E7", borderRadius: 10, padding: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <strong>{r.type}</strong>
                      <StatusBadge type="pending" label={`${r.status} (pending official review)`} />
                    </div>
                    <p style={{ fontSize: 12, color: "#5B6773" }}>{r.summary}</p>
                    <p style={{ fontSize: 11, color: "#7A8A96" }}>{r.submittedAt}</p>
                  </div>
                ))}
              </div>
            ) : !ctx.complaints?.length && !gradingHistory.length ? (
              <p style={{ color: "#5B6773" }}>Submitted requests will appear here once processed by the Embassy.</p>
            ) : null}
          </div>
        ) : null}
      </main>
      <PageFooter />
    </div>
  );
}

function NoticeBox({
  tone = "info",
  children,
}: {
  tone?: "info" | "warning" | "success" | "error";
  children: ReactNode;
}) {
  const palette = {
    info: { background: "#F7FAFC", border: "#E3EBF0", color: "#334155" },
    warning: { background: "#FFF7E6", border: "#F3D19C", color: "#8A5C00" },
    success: { background: "#EAF7EE", border: "#BBF7D0", color: "#166534" },
    error: { background: "#FEF2F1", border: "#FECACA", color: "#991B1B" },
  }[tone];

  return (
    <div
      style={{
        border: `1px solid ${palette.border}`,
        borderRadius: 10,
        padding: 12,
        background: palette.background,
        color: palette.color,
        fontSize: 13,
        lineHeight: 1.6,
      }}
    >
      {children}
    </div>
  );
}

function PendingArrivalPanel({ title, message }: { title: string; message: string }) {
  return (
    <FormCard title={title}>
      <NoticeBox tone="warning">{message}</NoticeBox>
      <p style={{ margin: 0, color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
        You can still use Overview, My Requests, and Change password while your arrival activation is pending.
      </p>
    </FormCard>
  );
}

function Field({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 11, color: "#7A8A96", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.5, overflowWrap: "anywhere" }}>{value}</div>
    </div>
  );
}

function FormCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 12,
        border: "1px solid #E3EBF0",
        padding: "clamp(14px, 3vw, 16px)",
        display: "grid",
        gap: 10,
        minWidth: 0,
      }}
    >
      <h3 style={{ color: "#2D4A6B" }}>{title}</h3>
      {children}
    </div>
  );
}
