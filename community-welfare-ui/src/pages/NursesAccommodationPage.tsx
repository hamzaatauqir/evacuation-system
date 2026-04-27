import { useState } from "react";
import { NursePortalGuard } from "../components/NursePortalGuard";
import { addLocalPortalRequest, getNursePortalContext } from "../lib/nursePortal";
import { useNavigate } from "react-router-dom";
import { FormPage, SuccessState } from "../components/FormPage";
import { Card, Grid } from "../components/Layout";
import { Btn } from "../components/Btn";
import { Icon } from "../components/Icon";
import { NoticeCard } from "../components/NoticeCard";
import { FInput, FSelect, FTextarea } from "../components/FormField";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

interface FormState {
  name?: string;
  id?: string;
  phone?: string;
  hospital?: string;
  currentAcc?: string;
  reqType?: string;
  address?: string;
  details?: string;
  urgency?: string;
}

export function NursesAccommodationPage() {
  const navigate = useNavigate();
  const nurse = getNursePortalContext();
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
      await api.post("/api/nurses/accommodation", {
        nurse_reference_id: (nurse?.referenceId || form.id || "").trim(),
        passport_number: (nurse?.passportNumber || form.id || "").trim(),
        current_accommodation_status: (form.currentAcc || "").trim(),
        requested_facility: (form.reqType || "").trim(),
        reason_remarks: (form.details || "").trim(),
      });
      addLocalPortalRequest({ type: "Accommodation", summary: (form.details || "Accommodation request submitted").toString() });
      setSubmitted(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const sidebar = (
    <Card style={{ borderTop: "3px solid #0369a1" }}>
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: T.navy,
          marginBottom: 10,
          display: "flex",
          gap: 8,
          alignItems: "center",
        }}
      >
        <Icon name="info" size={15} color="#0369a1" />
        Guidance
      </div>
      <p style={{ fontSize: 12, color: T.muted, lineHeight: 1.65, marginBottom: 10 }}>
        Accommodation requests are reviewed by the Community Welfare Wing in coordination with MOH and
        hospital HR departments.
      </p>
      <p style={{ fontSize: 12, color: T.muted, lineHeight: 1.65 }}>
        For urgent situations, contact the Embassy directly via phone or WhatsApp.
      </p>
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
          style={{ display: "flex", gap: 7, alignItems: "center", fontSize: 12, color: T.infoFg }}
        >
          <Icon name="phone" size={13} color={T.infoFg} />
          +965 5597 7292
        </a>
      </div>
    </Card>
  );

  return (
    <NursePortalGuard next="accommodation">
    <FormPage
      title="Accommodation Request"
      subtitle="Submit requests for MOH or private hospital accommodation-related facilitation"
      accentColor="#0a2d5c"
      backTo="/nurses"
      backLabel="Back to Nurses Home"
      sidebar={sidebar}
    >
      <Card>
        {submitted ? (
          <SuccessState message="Your accommodation request has been registered. The Community Welfare Wing will review and contact you." />
        ) : (
          <>
            <NoticeCard type="info" title="Before you submit">
              Supporting documents are requested by official email only. No file uploads required here.
            </NoticeCard>
            <div style={{ marginTop: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: T.navy, marginBottom: 16 }}>
                Nurse Identification
              </h3>
              <Grid cols={2} gap={14}>
                <FInput label="Full Name" req {...inp("name")} placeholder="As per passport" />
                <FInput
                  label="Passport / Civil ID"
                  req
                  {...inp("id")}
                  placeholder="Passport or Civil ID number"
                />
                <FInput
                  label="Phone / WhatsApp"
                  req
                  {...inp("phone")}
                  type="tel"
                  placeholder="+965 XXXX XXXX"
                />
                <FInput
                  label="Hospital / Employer"
                  req
                  {...inp("hospital")}
                  placeholder="Current employer name"
                />
              </Grid>
              <div style={{ height: 1, background: T.borderLt, margin: "18px 0" }} />
              <h3 style={{ fontSize: 15, fontWeight: 700, color: T.navy, marginBottom: 16 }}>
                Request Details
              </h3>
              <Grid cols={2} gap={14}>
                <FSelect
                  label="Current Accommodation Status"
                  req
                  {...inp("currentAcc")}
                  placeholder="Select"
                  options={[
                    "None — Seeking Accommodation",
                    "MOH Provided",
                    "Hospital Provided",
                    "Private",
                    "Embassy Shelter",
                  ]}
                />
                <FSelect
                  label="Type of Request"
                  req
                  {...inp("reqType")}
                  placeholder="Select"
                  options={[
                    "New Accommodation Placement",
                    "Transfer / Relocation",
                    "Maintenance / Repairs",
                    "Disputes with Landlord / Hospital",
                    "Other",
                  ]}
                />
              </Grid>
              <FInput label="Current Address / Location" {...inp("address")} placeholder="Current area in Kuwait" />
              <FTextarea
                label="Details of Issue or Request"
                req
                {...inp("details")}
                placeholder="Describe your accommodation situation and what assistance you need..."
                rows={4}
              />
              <FSelect
                label="Urgency Level"
                req
                {...inp("urgency")}
                placeholder="Select"
                options={["Normal (1–3 working days)", "Urgent (24 hours)", "Emergency (Immediate)"]}
              />
              {error && <p style={{ color: T.error, fontSize: 12, marginTop: 8 }}>{error}</p>}
            </div>
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
              <Btn variant="light" onClick={() => navigate("/nurses")}>
                Cancel
              </Btn>
              <Btn variant="primary" icon="check" onClick={submit} disabled={submitting}>
                {submitting ? "Submitting…" : "Submit Accommodation Request"}
              </Btn>
            </div>
          </>
        )}
      </Card>
    </FormPage>
    </NursePortalGuard>
  );
}
