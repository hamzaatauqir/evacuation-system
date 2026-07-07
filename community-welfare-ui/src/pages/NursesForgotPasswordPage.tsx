import { useState } from "react";
import { Link } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { NoticeCard } from "../components/NoticeCard";
import { API_BASE, api } from "../lib/api";

export function NursesForgotPasswordPage() {
  const [identity, setIdentity] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError("");
    setMessage("");
    if (!identity.trim()) {
      setError("Please enter your registered email or passport number (or Civil ID if you have one).");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post<{ ok?: boolean; message?: string }>("/api/nurses/forgot-password", {
        identity: identity.trim(),
      });
      setMessage(res.message || "If a matching nurse account exists, password reset instructions have been sent.");
    } catch (e) {
      setError((e as Error).message || `Could not reach backend at ${API_BASE}.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <main style={{ flex: 1, padding: 24, display: "grid", placeItems: "center" }}>
        <div style={{ maxWidth: 440, width: "100%", background: "#fff", border: "1px solid #E3EBF0", borderRadius: 14, padding: 28 }}>
          <h1 style={{ color: "#2D4A6B", marginBottom: 8, fontSize: 22 }}>Forgot password</h1>
          <p style={{ color: "#5B6773", marginBottom: 18, fontSize: 14, lineHeight: 1.65 }}>
            Enter the email or passport number associated with your nurse registration (or Civil ID if you have one on
            file). If we find a match, we will email reset instructions to the address on file.
          </p>
          <label style={{ display: "block", marginBottom: 14, fontSize: 13 }}>
            Email or passport (Civil ID if issued)
            <input className="f-input" value={identity} onChange={(e) => setIdentity(e.target.value)} />
          </label>
          <Btn variant="primary" onClick={submit} disabled={loading}>
            {loading ? "Submitting…" : "Send reset instructions"}
          </Btn>
          {message ? (
            <div style={{ marginTop: 16 }}>
              <NoticeCard type="info">{message}</NoticeCard>
            </div>
          ) : null}
          {error ? (
            <div style={{ marginTop: 16 }}>
              <NoticeCard type="warning">{error}</NoticeCard>
            </div>
          ) : null}
          <p style={{ marginTop: 20, fontSize: 13 }}>
            <Link to="/nurses/login" style={{ color: "#2563eb" }}>
              ← Back to login
            </Link>
          </p>
        </div>
      </main>
      <PageFooter />
    </div>
  );
}
