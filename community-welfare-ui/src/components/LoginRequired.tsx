import { Link } from "react-router-dom";
import { PublicHeader } from "./PublicHeader";
import { PageFooter } from "./PageFooter";
import { Btn } from "./Btn";

export function LoginRequired({ next }: { next: string }) {
  return (
    <div className="fade-in" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <PublicHeader />
      <main style={{ flex: 1, display: 'grid', placeItems: 'center', padding: 24 }}>
        <div style={{ maxWidth: 620, width: '100%', background: '#fff', borderRadius: 14, border: '1px solid #E3EBF0', padding: 24 }}>
          <h2 style={{ marginBottom: 8 }}>Nurse Portal Login Required</h2>
          <p style={{ color: '#5B6773', marginBottom: 16 }}>
            Please login or track your registration first to access nurse services.
          </p>
          <Link to={`/nurses/login?next=${encodeURIComponent(next)}`}>
            <Btn variant="primary">Open Nurse Portal Login</Btn>
          </Link>
        </div>
      </main>
      <PageFooter />
    </div>
  );
}
