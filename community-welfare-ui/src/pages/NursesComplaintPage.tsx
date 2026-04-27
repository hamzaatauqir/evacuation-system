import { useState } from "react";
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
  hospital?: string;
  category?: string;
  subject?: string;
  desc?: string;
  priority?: string;
}

const CATEGORIES = [
  "Salary / Unpaid Wages",
  "Workplace Issue",
  "Accommodation",
  "Civil ID / Residency",
  "Emergency / Safety",
  "Illegal Confinement",
  "Passport Retention",
  "Other",
];

export function NursesComplaintPage() {
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
      await api.post("/api/nurses/complaint", {
        nurse_reference_id: (form.id || "").trim(),
        passport_number: (form.id || "").trim(),
        verifier: (form.phone || "").trim(),
        complaint_category: (form.category || "").trim(),
        priority: (form.priority || "Normal").trim(),
        subject: (form.subject || "").trim(),
        description: (form.desc || "").trim(),
        preferred_contact_method: "WhatsApp",
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
    <FormPage
      title="Complaint / Welfare Issue"
      subtitle="Report workplace grievances, administrative issues, or urgent welfare concerns"
      accentColor="#3b0a0a"
      backTo="/nurses"
      backLabel="Back to Nurses Home"
    >
      <div style={{ marginBottom: 16 }}>
        <NoticeCard type="warning" title="For urgent safety concerns">
          Contact the Embassy directly at +965 5597 7292 without delay. Do not wait to submit a form.
        </NoticeCard>
      </div>
      <Card>
        {submitted ? (
          <SuccessState message="Your complaint has been registered. The Community Welfare Wing will review urgently and contact you." />
        ) : (
          <>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: T.navy, marginBottom: 16 }}>
              Your Information
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
                {...inp("hospital")}
                placeholder="Current employer"
              />
            </Grid>
            <div style={{ height: 1, background: T.borderLt, margin: "18px 0" }} />
            <h3 style={{ fontSize: 15, fontWeight: 700, color: T.navy, marginBottom: 14 }}>
              Complaint Category
            </h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill,minmax(175px,1fr))",
                gap: 10,
                marginBottom: 20,
              }}
            >
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  onClick={() => setForm((p) => ({ ...p, category: c }))}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 8,
                    border: `1.5px solid ${form.category === c ? T.error : T.borderLt}`,
                    background: form.category === c ? T.errorBg : T.surface,
                    fontSize: 12,
                    fontWeight: 600,
                    color: form.category === c ? T.error : T.muted,
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all .15s",
                  }}
                >
                  {c}
                </button>
              ))}
            </div>
            <FInput
              label="Issue Subject"
              req
              {...inp("subject")}
              placeholder="Brief title of your complaint"
            />
            <FTextarea
              label="Detailed Description"
              req
              {...inp("desc")}
              placeholder="Provide full details of the issue, dates, names, and any relevant information..."
              rows={5}
            />
            <FSelect
              label="Priority"
              req
              {...inp("priority")}
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
              <Btn variant="light" onClick={() => navigate("/nurses")}>
                Cancel
              </Btn>
              <Btn variant="danger" icon="alert" onClick={submit} disabled={submitting}>
                {submitting ? "Submitting…" : "Submit Complaint"}
              </Btn>
            </div>
          </>
        )}
      </Card>
    </FormPage>
  );
}
