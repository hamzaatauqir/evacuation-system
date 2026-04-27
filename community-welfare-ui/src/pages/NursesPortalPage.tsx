import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { StatusBadge } from "../components/StatusBadge";
import { Icon } from "../components/Icon";
import { getLocalPortalRequests, getNursePortalContext, clearNursePortalContext } from "../lib/nursePortal";

export function NursesPortalPage() {
  const navigate = useNavigate();
  const [ctx] = useState(() => getNursePortalContext());
  const requests = useMemo(() => getLocalPortalRequests(), []);

  if (!ctx) {
    navigate('/nurses/login');
    return null;
  }

  const statusType = (ctx.registrationStatus || '').toLowerCase().includes('resolved')
    ? 'resolved'
    : (ctx.registrationStatus || '').toLowerCase().includes('progress')
    ? 'processing'
    : 'pending';

  return (
    <div className="fade-in" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <PublicHeader />
      <main style={{ flex: 1, maxWidth: 1120, margin: '0 auto', width: '100%', padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, gap: 10, flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: 28, color: '#2D4A6B' }}>Nurse Portal Dashboard</h1>
          <Btn
            variant="light"
            onClick={() => {
              clearNursePortalContext();
              navigate('/nurses/login');
            }}
          >
            Logout / Clear Portal Session
          </Btn>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 14, marginBottom: 14 }}>
          <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E3EBF0', padding: 16 }}>
            <h3 style={{ marginBottom: 10, color: '#2D4A6B' }}>Nurse Profile Summary</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <Field label="Name" value={ctx.fullName || '-'} />
              <Field label="Reference ID" value={ctx.referenceId || '-'} />
              <Field label="Passport" value={ctx.passportMasked || '-'} />
              <Field label="Civil ID" value={ctx.civilIdMasked || '-'} />
              <Field label="Hospital" value={ctx.hospital || '-'} />
              <Field label="Mobile" value={ctx.mobile ? `***${ctx.mobile.slice(-3)}` : '-'} />
            </div>
          </div>

          <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E3EBF0', padding: 16 }}>
            <h3 style={{ marginBottom: 10, color: '#2D4A6B' }}>Registration Tracking</h3>
            <div style={{ marginBottom: 8 }}><StatusBadge type={statusType as any} label={ctx.registrationStatus || 'Pending'} /></div>
            <p style={{ color: '#5B6773', fontSize: 13 }}><strong>Last updated:</strong> {ctx.lastUpdated || '-'}</p>
            <p style={{ color: '#5B6773', fontSize: 13, marginTop: 8 }}><strong>Remarks:</strong> {ctx.remarks || 'No remarks yet.'}</p>
          </div>
        </div>

        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E3EBF0', padding: 16, marginBottom: 14 }}>
          <h3 style={{ marginBottom: 12, color: '#2D4A6B' }}>Services Available in Portal</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 10 }}>
            <ServiceLink to="/nurses/accommodation" icon="home" title="Accommodation Request" />
            <ServiceLink to="/nurses/complaint" icon="alert" title="Complaint / Welfare Issue" />
            <ServiceLink to="/nurses/leaving-notice" icon="exit" title="Leaving Notice / Exit" />
          </div>
        </div>

        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E3EBF0', padding: 16, marginBottom: 14 }}>
          <h3 style={{ marginBottom: 12, color: '#2D4A6B' }}>My Requests / History</h3>
          {ctx.complaints?.length ? (
            <div style={{ display: 'grid', gap: 8, marginBottom: 10 }}>
              {ctx.complaints.slice(0, 10).map((c, idx) => (
                <div key={c.complaint_id || idx} style={{ border: '1px solid #E3EBF0', borderRadius: 10, padding: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                    <strong>{c.subject || 'Complaint'}</strong>
                    <StatusBadge type={(c.status || '').toLowerCase().includes('resolved') ? 'resolved' : 'processing'} label={c.status || 'In Review'} />
                  </div>
                  <p style={{ fontSize: 12, color: '#5B6773' }}>Type: {c.category || '-'} | Submitted: {c.submitted_date || '-'}</p>
                </div>
              ))}
            </div>
          ) : null}

          {requests.length ? (
            <div style={{ display: 'grid', gap: 8 }}>
              {requests.map((r) => (
                <div key={r.id} style={{ border: '1px dashed #D8E0E7', borderRadius: 10, padding: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                    <strong>{r.type}</strong>
                    <StatusBadge type="pending" label={r.status} />
                  </div>
                  <p style={{ fontSize: 12, color: '#5B6773' }}>{r.summary}</p>
                  <p style={{ fontSize: 11, color: '#7A8A96' }}>{r.submittedAt}</p>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: '#5B6773' }}>Request history will appear here after submission or Embassy review.</p>
          )}
        </div>

        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E3EBF0', padding: 16 }}>
          <h3 style={{ marginBottom: 8, color: '#2D4A6B' }}>Help & Contact</h3>
          <p style={{ color: '#5B6773' }}>Email: parepkuwaitcwa37@gmail.com</p>
          <p style={{ color: '#5B6773' }}>Phone/WhatsApp: +965 5597 7292</p>
        </div>
      </main>
      <PageFooter />
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return <div><div style={{ fontSize: 11, color: '#7A8A96', marginBottom: 2 }}>{label}</div><div style={{ fontSize: 13, fontWeight: 600 }}>{value}</div></div>;
}

function ServiceLink({ to, icon, title }: { to: string; icon: any; title: string }) {
  return (
    <Link to={to} style={{ border: '1px solid #E3EBF0', borderRadius: 10, padding: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
      <Icon name={icon} size={18} color="#2D4A6B" />
      <div>
        <div style={{ fontWeight: 700, color: '#2D4A6B', fontSize: 13 }}>{title}</div>
        <div style={{ fontSize: 12, color: '#5B6773' }}>Open service form</div>
      </div>
    </Link>
  );
}
