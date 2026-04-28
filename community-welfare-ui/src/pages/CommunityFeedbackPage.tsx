import { useState, type ChangeEvent } from "react";
import { FormPage, SuccessState } from "../components/FormPage";
import { Card, Grid } from "../components/Layout";
import { FInput, FSelect, FTextarea } from "../components/FormField";
import { Btn } from "../components/Btn";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

type FormState = Record<string, string | boolean>;

export function CommunityFeedbackPage() {
  const [form, setForm] = useState<FormState>({});
  const [reference, setReference] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const bind = (key: string) => ({
    value: String(form[key] || ""),
    onChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm((prev) => ({ ...prev, [key]: e.target.value })),
  });

  async function submit() {
    setError("");
    setSubmitting(true);
    try {
      const res = await api.post<{ ok?: boolean; success?: boolean; reference?: string; error?: string; message?: string }>(
        "/api/welfare/feedback",
        form
      );
      if (!res.reference) {
        throw new Error(res.error || "Unable to submit at the moment. Please try again or contact the Community Welfare Wing.");
      }
      setReference(res.reference);
    } catch (err) {
      const msg = (err as Error).message || "";
      if (!msg || /failed to fetch|networkerror|request failed/i.test(msg)) {
        setError("Unable to submit at the moment. Please try again or contact the Community Welfare Wing.");
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <FormPage
      title="Community Feedback / Recommendations / Complaints"
      subtitle="Submit community welfare feedback, recommendations, service-related complaints, or suggestions for improvement. The Community Welfare Wing will review submissions and route them to the relevant officer where appropriate."
      accentColor="#2f7d4e"
      backLabel="Back to Services"
      backTo="/"
    >
      <Card>
        {reference ? (
          <SuccessState message={`Submission received. Reference: ${reference}`} />
        ) : (
          <>
            <Grid cols={2} gap={14}>
              <FInput label="Full name" req {...bind("name")} />
              <FInput label="Phone/WhatsApp" req {...bind("phone")} />
              <FInput label="Email" type="email" {...bind("email")} />
              <FSelect
                label="Category"
                req
                placeholder="Select"
                options={[
                  "Recommendation / Suggestion",
                  "Service Complaint",
                  "Welfare Concern",
                  "Employer / Workplace Concern",
                  "Consular Service Feedback",
                  "Other",
                ]}
                {...bind("category")}
              />
            </Grid>
            <FInput label="Subject" req {...bind("subject")} />
            <FTextarea label="Details" req rows={5} {...bind("details")} />
            <FSelect
              label="Preferred contact method"
              options={["Phone/WhatsApp", "Email", "No response needed"]}
              {...bind("preferred_contact_method")}
            />
            <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 13, lineHeight: 1.55 }}>
              <input
                type="checkbox"
                checked={Boolean(form.consent)}
                onChange={(e) => setForm((prev) => ({ ...prev, consent: e.target.checked }))}
              />
              I consent to the Community Welfare Wing reviewing this submission and contacting me where appropriate.
            </label>
            {error && <p style={{ color: T.error, fontSize: 12 }}>{error}</p>}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
              <Btn onClick={submit} disabled={submitting || !form.consent}>
                {submitting ? "Submitting..." : "Submit Feedback"}
              </Btn>
            </div>
          </>
        )}
      </Card>
    </FormPage>
  );
}
