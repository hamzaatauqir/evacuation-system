import { useState, type ChangeEvent } from "react";
import { FormPage, SuccessState } from "../components/FormPage";
import { Card, Grid } from "../components/Layout";
import { FInput, FTextarea } from "../components/FormField";
import { Btn } from "../components/Btn";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

type FormState = Record<string, string | boolean>;

export function LocatingAssistancePage() {
  const [form, setForm] = useState<FormState>({});
  const [reference, setReference] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const bind = (key: string) => ({
    value: String(form[key] || ""),
    onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((prev) => ({ ...prev, [key]: e.target.value })),
  });

  async function submit() {
    setError("");
    setSubmitting(true);
    try {
      const res = await api.post<{ ok: boolean; reference: string }>("/api/welfare/locating-assistance", form);
      setReference(res.reference);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <FormPage
      title="Request for Welfare Assistance in Locating / Contacting a Pakistani National in Kuwait"
      subtitle="Submit a welfare assistance request when a family member or concerned person is unable to contact a Pakistani national believed to be in Kuwait. The Embassy may review the information and, where appropriate, guide the applicant regarding available welfare and consular channels."
      accentColor={T.navy}
      backLabel="Back to Services"
      backTo="/"
    >
      <Card style={{ marginBottom: 18, background: "#fff7ed", borderColor: "#fed7aa" }}>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.7, color: "#7c2d12" }}>
          This form is for welfare assistance and preliminary information sharing. In emergencies or
          suspected criminal matters, the requester should also contact the relevant local authorities.
          Submission of this form does not replace any legal or police reporting requirement.
        </p>
      </Card>
      <Card>
        {reference ? (
          <SuccessState message={`Your request has been received. If you provided an email address, please check your inbox and verify your email address to receive future updates. Reference: ${reference}`} />
        ) : (
          <>
            <h2 style={{ fontSize: 16, fontWeight: 800, color: T.navy, marginBottom: 14 }}>Requester Details</h2>
            <Grid cols={2} gap={14}>
              <FInput label="Requester full name" req {...bind("requester_name")} />
              <FInput label="Relationship to person" {...bind("requester_relationship")} />
              <FInput label="Requester phone/WhatsApp" req {...bind("requester_phone")} />
              <FInput label="Requester email" type="email" {...bind("requester_email")} />
              <FInput label="Requester country/location" {...bind("requester_location")} />
            </Grid>
            <h2 style={{ fontSize: 16, fontWeight: 800, color: T.navy, margin: "18px 0 14px" }}>Person Concerned</h2>
            <Grid cols={2} gap={14}>
              <FInput label="Full name of Pakistani national" req {...bind("subject_name")} />
              <FInput label="Passport number if available" {...bind("subject_passport")} />
              <FInput label="CNIC if available" {...bind("subject_cnic")} />
              <FInput label="Civil ID if available" {...bind("subject_civil_id")} />
              <FInput label="Last known phone number" {...bind("subject_phone")} />
              <FInput label="Last date of contact" type="date" {...bind("last_contact_date")} />
            </Grid>
            <FInput label="Last known address in Kuwait" {...bind("subject_address")} />
            <FInput label="Last known workplace/employer" {...bind("subject_workplace")} />
            <FTextarea label="Brief reason for concern" req rows={4} {...bind("concern_summary")} />
            <FInput label="Any police report/reference if available" {...bind("police_reference")} />
            <FTextarea label="Supporting details" rows={4} {...bind("details")} />
            <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 13, lineHeight: 1.55 }}>
              <input
                type="checkbox"
                checked={Boolean(form.declaration)}
                onChange={(e) => setForm((prev) => ({ ...prev, declaration: e.target.checked }))}
              />
              I confirm that the information provided is true to the best of my knowledge and I understand
              that the Embassy may contact me for verification.
            </label>
            {error && <p style={{ color: T.error, fontSize: 12 }}>{error}</p>}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
              <Btn onClick={submit} disabled={submitting || !form.declaration}>
                {submitting ? "Submitting..." : "Submit Request"}
              </Btn>
            </div>
          </>
        )}
      </Card>
    </FormPage>
  );
}
