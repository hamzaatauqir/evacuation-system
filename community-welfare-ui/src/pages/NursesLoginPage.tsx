import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { NoticeCard } from "../components/NoticeCard";
import { API_BASE, api } from "../lib/api";
import { buildPortalContextFromApiData, setNursePortal } from "../lib/nursePortal";

export function NursesLoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const next = params.get("next") || "portal";

  async function login() {
    if (!identity.trim() || !password) {
      setError("Please enter your email or passport number and your password.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await api.post<{ success?: boolean; error?: string; data?: Record<string, unknown> }>(
        "/api/nurses/login",
        {
          identity: identity.trim(),
          password,
        }
      );
      if (!res.success || !res.data) {
        setError(res.error || "Login failed.");
        return;
      }
      const ctx = buildPortalContextFromApiData(res.data);
      setNursePortal(ctx);
      const nextRoute =
        next === "accommodation"
          ? "/nurses/portal?tab=stay"
          : next === "complaint"
            ? "/nurses/portal?tab=complaint"
            : next === "leaving" || next === "leaving-notice"
              ? "/nurses/portal?tab=leaving"
              : "/nurses/portal";
      navigate(nextRoute, { replace: true });
    } catch (err) {
      setError((err as Error).message || `Could not reach backend at ${API_BASE}.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <main style={{ flex: 1, padding: 24, display: "grid", placeItems: "center" }}>
        <div
          style={{
            maxWidth: 440,
            width: "100%",
            background: "#fff",
            border: "1px solid #E3EBF0",
            borderRadius: 14,
            padding: 28,
            boxShadow: "0 8px 32px rgba(45,74,107,.08)",
          }}
        >
          <h1 style={{ color: "#2D4A6B", marginBottom: 6, fontSize: 22 }}>Nurse Portal Login</h1>
          <p style={{ color: "#5B6773", marginBottom: 20, fontSize: 14, lineHeight: 1.6 }}>
            Sign in with the email or passport number you used at registration (or your Civil ID if you have one on
            file), and your password.
          </p>
          <label style={{ display: "block", marginBottom: 12, fontSize: 13, color: "#334155" }}>
            Email or passport (Civil ID if issued)
            <input
              className="f-input"
              value={identity}
              onChange={(e) => setIdentity(e.target.value)}
              autoComplete="username"
              placeholder="Email or passport (Civil ID if issued)"
            />
          </label>
          <label style={{ display: "block", marginBottom: 8, fontSize: 13, color: "#334155" }}>
            Password
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                className="f-input"
                style={{ flex: 1 }}
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="Your password"
              />
              <button
                type="button"
                className="f-input"
                style={{ width: "auto", cursor: "pointer", whiteSpace: "nowrap", padding: "8px 12px" }}
                onClick={() => setShowPw((s) => !s)}
              >
                {showPw ? "Hide" : "Show"}
              </button>
            </div>
          </label>
          <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 12 }}>
            <Btn variant="primary" onClick={login} disabled={loading}>
              {loading ? "Signing in…" : "Login"}
            </Btn>
            <Link to="/nurses/forgot-password" style={{ fontSize: 13, color: "#2563eb", textAlign: "center" }}>
              Forgot password?
            </Link>
            <Link to="/nurses/register">
              <Btn variant="light" style={{ width: "100%" }}>
                New nurse registration
              </Btn>
            </Link>
          </div>
          {error ? (
            <div style={{ marginTop: 16 }}>
              <NoticeCard type="warning" title="Unable to sign in">
                {error}
              </NoticeCard>
            </div>
          ) : null}
        </div>
      </main>
      <PageFooter />
    </div>
  );
}
