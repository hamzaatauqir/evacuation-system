import { useState } from "react";
import { NursePortalGuard } from "../components/NursePortalGuard";
import { addLocalPortalRequest, getNursePortalContext } from "../lib/nursePortal";
import { useNavigate } from "react-router-dom";
import { FormPage, SuccessState } from "../components/FormPage";
import { Card, Grid } from "../components/Layout";
import { Btn } from "../components/Btn";
import { NoticeCard } from "../components/NoticeCard";
import { FInput, FSelect, FTextarea } from "../components/FormField";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

interface FormState {
  name?: string;
  id?: string;
  phone?: string;
  current?: string;
  date?: string;
  reason?: string;
  dest?: string;
  notes?: string;
}

export function NursesLeavingNoticePage() {
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
      await api.post("/api/nurses/leave-notice", {
        nurse_reference_id: (nurse?.referenceId || form.id || "").trim(),
        passport_number: (nurse?.passportNumber || form.id || "").trim(),
        current_facility: (form.current || "").trim(),
        room_number: "",
        intended_leaving_date: (form.date || "").trim(),
        reason: (form.reason || "").trim(),
      });
      addLocalPortalRequest({ type: "Leaving Notice", summary: (form.reason || "Leaving notice submitted").toString() });
      setSubmitted(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <NursePortalGuard next="leaving-notice">
    <FormPage
      title="Leaving Notice / Exit from Accommodation"
      subtitle="Submit official notification before vacating Embassy or hospital-provided accommodation"
      backTo="/nurses"
      backLabel="Back to Nurses Home"
    >
      <Card>
        {submitted ? (
          <SuccessState message="Your leaving notice has been received and registered with the Community Welfare Wing." />
        ) : (
          <>
            <NoticeCard type="warning">
              Please submit this notice at least 72 hours before your intended leaving date.
            </NoticeCard>
            <div style={{ marginTop: 20 }}>
              <Grid cols={2} gap={14}>
                <FInput label="Full Name" req {...inp("name")} placeholder="As per passport" />
                <FInput label="Passport / Civil ID" req {...inp("id")} placeholder="Document number" />
                <FInput
                  label="Phone / WhatsApp"
                  req
                  {...inp("phone")}
                  type="tel"
                  placeholder="+965 XXXX XXXX"
                />
                <FInput
                  label="Current Accommodation"
                  req
                  {...inp("current")}
                  placeholder="Address / Facility name"
                />
                <FInput label="Intended Leaving Date" req {...inp("date")} type="date" />
                <FSelect
                  label="Reason for Leaving"
                  req
                  {...inp("reason")}
                  placeholder="Select"
                  options={[
                    "Job Transfer / New Employer",
                    "Return to Pakistan",
                    "Transfer to Private Housing",
                    "Contract End",
                    "Medical Reason",
                    "Other",
                  ]}
                />
              </Grid>
              <FInput
                label="Destination / New Accommodation"
                {...inp("dest")}
                placeholder="Where are you moving to?"
              />
              <FTextarea
                label="Additional Notes"
                {...inp("notes")}
                placeholder="Any other relevant information..."
                rows={3}
              />
              {error && <p style={{ color: T.error, fontSize: 12 }}>{error}</p>}
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
              <Btn variant="navy" icon="check" onClick={submit} disabled={submitting}>
                {submitting ? "Submitting…" : "Submit Leaving Notice"}
              </Btn>
            </div>
          </>
        )}
      </Card>
    </FormPage>
    </NursePortalGuard>
  );
}
