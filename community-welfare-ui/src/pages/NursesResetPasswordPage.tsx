import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { NoticeCard } from "../components/NoticeCard";
import { API_BASE, api } from "../lib/api";

export function NursesResetPasswordPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError("");
    if (!token) {
      setError("This reset link is missing a token. Please use the link from your email.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post<{ success?: boolean; error?: string; message?: string }>("/api/nurses/reset-password", {
        token,
        new_password: password,
        confirm_password: confirm,
      });
      if (!res.success) {
        setError(res.error || "Reset failed.");
        return;
      }
      setDone(true);
      setTimeout(() => navigate("/nurses/login", { replace: true }), 2500);
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
          <h1 style={{ color: "#2D4A6B", marginBottom: 8, fontSize: 22 }}>Set a new password</h1>
          <p style={{ color: "#5B6773", marginBottom: 18, fontSize: 14 }}>
            Choose a new password (at least 8 characters, including one letter and one number).
          </p>
          {done ? (
            <NoticeCard type="info">Your password has been updated. Redirecting to login…</NoticeCard>
          ) : (
            <>
              <label style={{ display: "block", marginBottom: 10, fontSize: 13 }}>
                New password
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    className="f-input"
                    style={{ flex: 1 }}
                    type={show ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                  <button type="button" className="f-input" style={{ cursor: "pointer" }} onClick={() => setShow((s) => !s)}>
                    {show ? "Hide" : "Show"}
                  </button>
                </div>
              </label>
              <label style={{ display: "block", marginBottom: 14, fontSize: 13 }}>
                Confirm new password
                <input
                  className="f-input"
                  type={show ? "text" : "password"}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
              <Btn variant="primary" onClick={submit} disabled={loading}>
                {loading ? "Saving…" : "Save new password"}
              </Btn>
            </>
          )}
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
