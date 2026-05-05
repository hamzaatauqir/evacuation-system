import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AdminLayout } from "../components/AdminLayout";
import { Btn } from "../components/Btn";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

type PendingAccountRow = {
  account_id?: number;
  nurse_registration_id?: number;
  reference_id?: string;
  full_name?: string;
  passport_number?: string;
  cnic?: string;
  civil_id?: string;
  mobile_full?: string;
  email?: string;
  registration_status?: string;
  account_status?: string;
  arrival_batch_id?: number | null;
  batch_code?: string;
  arrival_date?: string;
  arrival_batch_status?: string;
  account_created_at?: string;
  registration_created_at?: string;
};

type PendingAccountsResponse = {
  success?: boolean;
  feature_enabled?: boolean;
  total?: number;
  items?: PendingAccountRow[];
  error?: string;
};

export function AdminNursePendingAccountsPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<PendingAccountRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        setLoading(true);
        const res = await api.get<PendingAccountsResponse>("/api/admin/nurses/pending-accounts");
        if (!live) return;
        if (!res.success) {
          throw new Error(res.error || "Could not load pending nurse housing accounts.");
        }
        setRows(res.items || []);
        setError("");
      } catch (err) {
        if (!live) return;
        setRows([]);
        setError((err as Error).message || "Could not load pending nurse housing accounts.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      [
        row.reference_id,
        row.full_name,
        row.passport_number,
        row.cnic,
        row.civil_id,
        row.email,
        row.batch_code,
      ]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [rows, search]);

  return (
    <AdminLayout>
      <div className="fade-in admin-page-shell admin-page-content">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 14,
            flexWrap: "wrap",
            marginBottom: 20,
          }}
        >
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: T.navy }}>Pending Nurse Accounts</h1>
            <p style={{ marginTop: 4, color: T.muted, fontSize: 13 }}>
              New nurse registrations stay here until their arrival batch is marked ARRIVED.
            </p>
          </div>
          <div className="admin-page-actions">
            <Btn variant="light" onClick={() => navigate("/admin/nurses")}>Back to Nurses</Btn>
            <Btn variant="navy" onClick={() => navigate("/admin/nurses/arrival-batches")}>Arrival Batches</Btn>
          </div>
        </div>

        <Card style={{ marginBottom: 16 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div>
              <div style={{ fontSize: 12, color: T.mutedLt, textTransform: "uppercase", letterSpacing: ".06em" }}>
                Queue
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color: T.navy }}>{filtered.length}</div>
            </div>
            <label style={{ minWidth: 280, flex: "1 1 280px", color: T.muted, fontSize: 13 }}>
              Search
              <input
                className="f-input"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Reference, name, passport, CNIC, batch"
              />
            </label>
          </div>
        </Card>

        {error ? (
          <div
            style={{
              marginBottom: 16,
              background: "#FEF2F1",
              border: "1px solid #FECACA",
              color: "#991B1B",
              borderRadius: 10,
              padding: 12,
            }}
          >
            {error}
          </div>
        ) : null}

        <Card pad={0}>
          {loading ? (
            <div style={{ padding: 24, color: T.muted }}>Loading pending accounts…</div>
          ) : filtered.length ? (
            <div style={{ overflowX: "auto" }}>
              <table className="a-table">
                <thead>
                  <tr>
                    <th>Nurse</th>
                    <th>Batch</th>
                    <th>Arrival Date</th>
                    <th>Contact</th>
                    <th>Registration</th>
                    <th>Housing</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.account_id || row.nurse_registration_id || row.reference_id}>
                      <td>
                        <div style={{ display: "grid", gap: 4 }}>
                          <strong style={{ color: T.navy }}>{row.full_name || "Nurse"}</strong>
                          <span style={{ fontSize: 12, color: T.muted }}>
                            {row.reference_id || "—"} | Passport: {row.passport_number || "—"}
                          </span>
                          <span style={{ fontSize: 12, color: T.muted }}>
                            CNIC: {row.cnic || "—"} | Civil ID: {row.civil_id || "—"}
                          </span>
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "grid", gap: 4 }}>
                          <strong>{row.batch_code || "Unassigned"}</strong>
                          <StatusBadge
                            type={(row.arrival_batch_status || "").toUpperCase() === "ARRIVED" ? "resolved" : "pending"}
                            label={row.arrival_batch_status || "PLANNED"}
                          />
                        </div>
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>{row.arrival_date || "—"}</td>
                      <td>
                        <div style={{ display: "grid", gap: 4 }}>
                          <span>{row.mobile_full || "—"}</span>
                          <span style={{ fontSize: 12, color: T.muted }}>{row.email || "—"}</span>
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "grid", gap: 4 }}>
                          <StatusBadge type="info" label={row.registration_status || "Pending Review"} />
                          <span style={{ fontSize: 12, color: T.muted }}>
                            {row.registration_created_at || row.account_created_at || "—"}
                          </span>
                        </div>
                      </td>
                      <td>
                        <StatusBadge type="pending" label={row.account_status || "PENDING_ARRIVAL"} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 24, color: T.muted }}>
              No pending-arrival nurse housing accounts are waiting right now.
            </div>
          )}
        </Card>
      </div>
    </AdminLayout>
  );
}
