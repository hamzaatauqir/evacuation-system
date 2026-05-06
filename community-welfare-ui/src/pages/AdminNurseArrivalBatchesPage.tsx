import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AdminLayout } from "../components/AdminLayout";
import { Btn } from "../components/Btn";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

type ArrivalBatchRow = {
  id?: number;
  batch_code?: string;
  arrival_date?: string;
  status?: string;
  remarks?: string;
  arrived_at?: string;
  arrived_by?: string;
  linked_accounts?: number;
  pending_accounts?: number;
  active_accounts?: number;
  created_at?: string;
};

type ArrivalBatchesResponse = {
  success?: boolean;
  feature_enabled?: boolean;
  total?: number;
  items?: ArrivalBatchRow[];
  error?: string;
};

type MarkArrivedResponse = {
  success?: boolean;
  activated_count?: number;
  message?: string;
  error?: string;
};

function normalizeBatchNumber(value?: string) {
  const match = String(value || "").trim().match(/\d+/);
  return match ? match[0] : "";
}

export function AdminNurseArrivalBatchesPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<ArrivalBatchRow[]>([]);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    try {
      const res = await api.get<ArrivalBatchesResponse>("/api/admin/nurses/arrival-batches");
      if (!res.success) {
        throw new Error(res.error || "Could not load arrival batches.");
      }
      setRows(res.items || []);
      setError("");
    } catch (err) {
      setRows([]);
      setError((err as Error).message || "Could not load arrival batches.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function markArrived(batchId: number) {
    setBusyId(batchId);
    setFlash("");
    setError("");
    try {
      const res = await api.post<MarkArrivedResponse>("/api/admin/nurses/arrival-batches/mark-arrived", {
        batch_id: batchId,
      });
      if (!res.success) {
        throw new Error(res.error || "Arrival batch could not be updated.");
      }
      setFlash(res.message || "Arrival batch marked ARRIVED.");
      await load();
    } catch (err) {
      setError((err as Error).message || "Arrival batch could not be updated.");
    } finally {
      setBusyId(null);
    }
  }

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
            <h1 style={{ fontSize: 22, fontWeight: 800, color: T.navy }}>Arrival Batches</h1>
            <p style={{ marginTop: 4, color: T.muted, fontSize: 13 }}>
              Marking a batch ARRIVED activates all linked nurse accounts still waiting in PENDING_ARRIVAL.
            </p>
          </div>
          <div className="admin-page-actions">
            <Btn variant="light" onClick={() => navigate("/admin/nurses")}>Back to Nurses</Btn>
            <Btn variant="navy" onClick={() => navigate("/admin/nurses/pending-accounts")}>Pending Accounts</Btn>
          </div>
        </div>

        {flash ? (
          <div
            style={{
              marginBottom: 16,
              background: "#EAF7EE",
              border: "1px solid #BBF7D0",
              color: "#166534",
              borderRadius: 10,
              padding: 12,
            }}
          >
            {flash}
          </div>
        ) : null}

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
            <div style={{ padding: 24, color: T.muted }}>Loading arrival batches…</div>
          ) : rows.length ? (
            <div style={{ overflowX: "auto" }}>
              <table className="a-table">
                <thead>
                  <tr>
                    <th>Batch</th>
                    <th>Arrival Date</th>
                    <th>Status</th>
                    <th>Linked</th>
                    <th>Pending</th>
                    <th>Active</th>
                    <th>Arrival Log</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const arrived = (row.status || "").toUpperCase() === "ARRIVED";
                    const showAction = !arrived || (row.pending_accounts || 0) > 0;
                    const batchNumber = normalizeBatchNumber(row.batch_code) || row.batch_code || "Batch";
                    return (
                      <tr key={row.id || row.batch_code}>
                        <td>
                          <div style={{ display: "grid", gap: 4 }}>
                            <strong style={{ color: T.navy }}>{batchNumber}</strong>
                            <span style={{ fontSize: 12, color: T.muted }}>{row.created_at || "—"}</span>
                          </div>
                        </td>
                        <td style={{ whiteSpace: "nowrap" }}>{row.arrival_date || "—"}</td>
                        <td>
                          <StatusBadge type={arrived ? "resolved" : "pending"} label={row.status || "PLANNED"} />
                        </td>
                        <td>{row.linked_accounts || 0}</td>
                        <td>{row.pending_accounts || 0}</td>
                        <td>{row.active_accounts || 0}</td>
                        <td>
                          <div style={{ display: "grid", gap: 4 }}>
                            <span>{row.arrived_at || "—"}</span>
                            <span style={{ fontSize: 12, color: T.muted }}>{row.arrived_by || "—"}</span>
                          </div>
                        </td>
                        <td>
                          {showAction && row.id ? (
                            <Btn
                              variant={arrived ? "light" : "primary"}
                              size="sm"
                              disabled={busyId === row.id}
                              onClick={() => markArrived(row.id as number)}
                            >
                              {busyId === row.id
                                ? "Updating..."
                                : arrived
                                  ? "Re-sync Pending"
                                  : "Mark ARRIVED"}
                            </Btn>
                          ) : (
                            <span style={{ color: T.muted, fontSize: 12 }}>No action needed</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 24, color: T.muted }}>
              No arrival batches have been created yet. New nurse registrations with batch numbers will populate this list.
            </div>
          )}
        </Card>
      </div>
    </AdminLayout>
  );
}
