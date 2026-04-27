import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { NoticeCard } from "../components/NoticeCard";
import { API_BASE, api } from "../lib/api";
import { buildPortalContextFromTrackResponse, setNursePortalContext } from "../lib/nursePortal";

export function NursesLoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [identity, setIdentity] = useState("");
  const [verifier, setVerifier] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const next = params.get('next') || 'portal';

  async function lookup() {
    if (!identity.trim() || !verifier.trim()) {
      setError('Please provide identity and verifier details.');
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await api.post<{ success?: boolean; error?: string; data?: any }>("/api/nurses/track", {
        identity: identity.trim(),
        verifier: verifier.trim(),
      });
      if (!res.success || !res.data) {
        setError(res.error || 'No matching registration found.');
        return;
      }
      const ctx = buildPortalContextFromTrackResponse(res.data);
      setNursePortalContext(ctx);
      const nextRoute = next === 'accommodation' ? '/nurses/accommodation' : next === 'complaint' ? '/nurses/complaint' : next === 'leaving-notice' ? '/nurses/leaving-notice' : '/nurses/portal';
      navigate(nextRoute, { replace: true });
    } catch (err) {
      setError((err as Error).message || `Could not reach backend at ${API_BASE}.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fade-in" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <PublicHeader />
      <main style={{ flex: 1, padding: 24, display: 'grid', placeItems: 'center' }}>
        <div style={{ maxWidth: 700, width: '100%', background: '#fff', border: '1px solid #E3EBF0', borderRadius: 14, padding: 24 }}>
          <h1 style={{ color: '#2D4A6B', marginBottom: 8 }}>Existing Nurse Login / Track Registration</h1>
          <p style={{ color: '#5B6773', marginBottom: 16 }}>
            Enter your registration reference/passport as identity and provide your mobile/CNIC/Civil ID as verifier.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <label>
              Identity (Reference or Passport)
              <input className="f-input" value={identity} onChange={(e) => setIdentity(e.target.value)} placeholder="e.g. NUR-00001 or passport" />
            </label>
            <label>
              Verifier (Mobile, Civil ID, or CNIC)
              <input className="f-input" value={verifier} onChange={(e) => setVerifier(e.target.value)} placeholder="Enter verifier" />
            </label>
          </div>
          <div style={{ marginTop: 14 }}>
            <Btn variant="primary" onClick={lookup} disabled={loading}>{loading ? 'Verifying…' : 'Login / Track'}</Btn>
          </div>
          {error ? <div style={{ marginTop: 14 }}><NoticeCard type="warning" title="Unable to login">{error}</NoticeCard></div> : null}
        </div>
      </main>
      <PageFooter />
    </div>
  );
}
