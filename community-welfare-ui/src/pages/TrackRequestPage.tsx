import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FormPage } from "../components/FormPage";
import { Card } from "../components/Layout";
import { FInput } from "../components/FormField";
import { Btn } from "../components/Btn";
import { T } from "../lib/tokens";

type PublicNote = {
  note?: string;
  created_at?: string;
};

type TrackResult = {
  success: boolean;
  found: boolean;
  reference?: string;
  service_type?: string;
  submitted_at?: string;
  status?: string;
  last_updated?: string;
  current_stage?: string;
  message?: string;
  public_notes?: PublicNote[];
  next_step?: string;
  error?: string;
};

const REQUEST_TRACK_API_BASE = import.meta.env.VITE_API_BASE_URL || "https://portal.cwakuwait.com";

export function TrackRequestPage() {
  const navigate = useNavigate();
  const [reference, setReference] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TrackResult | null>(null);
  const [error, setError] = useState("");

  async function trackRequest() {
    const value = reference.trim().toUpperCase();
    if (!value) {
      setError("Please enter your reference number.");
      setResult(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const url = `${REQUEST_TRACK_API_BASE}/api/public-request-track?reference=${encodeURIComponent(value)}`;
      const res = await fetch(url, { method: "GET" });
      const data = (await res.json().catch(() => ({}))) as TrackResult;
      if (!res.ok) {
        throw new Error(data.error || "Unable to track the request at the moment. Please try again later.");
      }
      if (data.success && data.found) {
        setResult(data);
      } else if (data.found === false) {
        setResult(data);
      } else {
        setError("Unable to track the request at the moment. Please try again later.");
        setResult(null);
      }
    } catch (_err) {
      setError("Unable to track the request at the moment. Please try again later.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const notes = result?.public_notes || [];

  return (
    <FormPage
      title="Track Your Request"
      subtitle="Enter your reference number to view the current public status of your request submitted through the Community Welfare Wing portal."
      accentColor="#1f3a57"
      backLabel="Back to Services"
      backTo="/"
    >
      <Card>
        <FInput
          label="Reference Number"
          req
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          placeholder="CWA-FBK-2026-0004 / CWA-LOC-2026-0001 / LEGAL-2026-0001 / OPF-2026-0001 / DC-2026-0001 / NUR-00003 / NCMP-00001"
        />
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 18 }}>
          <Btn onClick={trackRequest} disabled={loading}>
            {loading ? "Tracking..." : "Track Request"}
          </Btn>
        </div>

        {error && <p style={{ marginTop: 12, color: T.error, fontSize: 13 }}>{error}</p>}

        {result?.found === false && (
          <div style={{ marginTop: 18, padding: 14, borderRadius: 12, background: "#fff7ed", border: "1px solid #fed7aa" }}>
            <p style={{ margin: 0, color: "#9a3412", fontSize: 13 }}>
              {result.error || "No request was found for this reference number. Please check the reference and try again."}
            </p>
          </div>
        )}

        {result?.success && result.found && (
          <div style={{ marginTop: 22, borderTop: `1px solid ${T.borderLt}`, paddingTop: 18 }}>
            <h3 style={{ marginTop: 0, marginBottom: 14, color: T.navy }}>Request Status</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12 }}>
              <Info label="Reference Number" value={result.reference} />
              <Info label="Service Type" value={result.service_type} />
              <Info label="Current Status" value={result.status} />
              <Info label="Submitted Date" value={result.submitted_at} />
              <Info label="Last Updated" value={result.last_updated} />
              <Info label="Current Stage" value={result.current_stage} />
              <Info label="What happens next" value={result.next_step} spanAll />
            </div>
            <div style={{ marginTop: 16, padding: 12, borderRadius: 10, background: "#eff6ff", border: "1px solid #bfdbfe" }}>
              <p style={{ margin: 0, color: "#1e3a8a", fontSize: 13 }}>{result.message || "Your request is being reviewed."}</p>
            </div>
            <h4 style={{ marginTop: 18, marginBottom: 10, color: T.navy }}>Latest Public Updates</h4>
            {notes.length === 0 ? (
              <p style={{ margin: 0, fontSize: 13, color: T.muted }}>
                No public updates are available yet. Please check again later.
              </p>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {notes.map((item, idx) => (
                  <div key={`${item.created_at || "note"}-${idx}`} style={{ padding: 12, border: `1px solid ${T.borderLt}`, borderRadius: 10 }}>
                    <p style={{ margin: 0, fontSize: 13, color: T.navy }}>{item.note || ""}</p>
                    {item.created_at && (
                      <p style={{ margin: "6px 0 0", fontSize: 12, color: T.muted }}>Updated: {item.created_at}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 22 }}>
          <Btn variant="light" onClick={() => navigate("/")}>Back to Services</Btn>
          <Btn variant="secondary" onClick={() => navigate("/community-feedback")}>Submit Feedback / Complaint</Btn>
          <Btn variant="ghost" onClick={() => window.location.assign("mailto:parepkuwaitcwa37@gmail.com")}>
            Contact Community Welfare Wing
          </Btn>
        </div>
      </Card>
    </FormPage>
  );
}

function Info({ label, value, spanAll }: { label: string; value?: string; spanAll?: boolean }) {
  return (
    <div
      style={{
        border: `1px solid ${T.borderLt}`,
        borderRadius: 10,
        padding: 10,
        background: T.surface,
        gridColumn: spanAll ? "1 / -1" : undefined,
      }}
    >
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13, color: T.navy, lineHeight: 1.45 }}>{value || "-"}</div>
    </div>
  );
}
