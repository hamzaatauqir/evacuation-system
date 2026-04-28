import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { AdminLayout } from "../components/AdminLayout";
import { AdminKpiCard } from "../components/AdminKpiCard";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { Btn } from "../components/Btn";
import { Icon } from "../components/Icon";
import { T, type StatusType } from "../lib/tokens";
import { api } from "../lib/api";

interface WelfareCase {
  id: number;
  case_reference: string;
  case_type: string;
  category: string;
  requester_name: string;
  requester_phone: string;
  requester_email: string;
  requester_location: string;
  subject_name: string;
  concern_summary: string;
  details: string;
  priority: string;
  status: string;
  assigned_to: string;
  escalation_level: string;
  created_at: string;
}

interface WelfareResponse {
  items: WelfareCase[];
  kpis: Record<string, number>;
}

const statusType = (value: string): StatusType => {
  const v = value.toLowerCase();
  if (v.includes("resolved")) return "resolved";
  if (v.includes("closed")) return "closed";
  if (v.includes("assigned")) return "assigned";
  if (v.includes("new")) return "new";
  if (v.includes("high") || v.includes("urgent")) return "urgent";
  return "processing";
};

export function AdminWelfareCasesPage() {
  const location = useLocation();
  const mode = location.pathname.includes("my-cases")
    ? "my"
    : location.pathname.includes("ambassador-review")
    ? "ambassador"
    : "all";
  const title = mode === "my" ? "My Assigned Cases" : mode === "ambassador" ? "Ambassador Review Queue" : "Welfare Cases";
  const [items, setItems] = useState<WelfareCase[]>([]);
  const [kpis, setKpis] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<WelfareCase | null>(null);
  const [error, setError] = useState("");

  const query = useMemo(() => {
    const p = new URLSearchParams();
    if (mode === "my") p.set("scope", "my");
    if (mode === "ambassador") p.set("escalation_level", "ambassador_review");
    return p.toString();
  }, [mode]);

  useEffect(() => {
    let active = true;
    api
      .get<WelfareResponse>(`/api/admin/welfare-cases?${query}`)
      .then((res) => {
        if (!active) return;
        setItems(res.items || []);
        setKpis(res.kpis || {});
      })
      .catch((err) => active && setError((err as Error).message));
    return () => {
      active = false;
    };
  }, [query]);

  return (
    <AdminLayout>
      <div style={{ flex: 1, overflow: "auto" }} className="fade-in">
        <div
          style={{
            background: T.surface,
            borderBottom: `1px solid ${T.borderLt}`,
            padding: "16px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, color: T.navy }}>{title}</h1>
            <p style={{ fontSize: 12, color: T.muted, marginTop: 2 }}>Unified assignment and action tracking</p>
          </div>
        </div>
        <div style={{ padding: "20px 24px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 12, marginBottom: 20 }}>
            <AdminKpiCard label="Total Welfare Cases" value={kpis.total || 0} accent={T.navy} icon="heart" />
            <AdminKpiCard label="New" value={kpis.new || 0} accent="#2563eb" icon="note" />
            <AdminKpiCard label="Assigned" value={kpis.assigned || 0} accent={T.green} icon="user" />
            <AdminKpiCard label="Assigned to Me" value={kpis.assigned_to_me || 0} accent="#6b21a8" icon="star" />
            <AdminKpiCard label="Ambassador Review" value={kpis.ambassador_review || 0} accent={T.error} icon="flag" />
            <AdminKpiCard label="Resolved This Week" value={kpis.resolved_this_week || 0} accent={T.successFg} icon="check" />
          </div>
          {error && <p style={{ color: T.error, fontSize: 12 }}>{error}</p>}
          <Card pad={0} style={{ overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="a-table">
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Case Type</th>
                    <th>Requester</th>
                    <th>Person/Subject</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Assigned To</th>
                    <th>Escalation</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <tr key={c.id} onClick={() => setSelected(c)}>
                      <td style={{ fontWeight: 800, color: T.navy }}>{c.case_reference}</td>
                      <td>{c.case_type}</td>
                      <td>{c.requester_name}</td>
                      <td>{c.subject_name || c.category}</td>
                      <td><StatusBadge type={statusType(c.priority)} label={c.priority || "Normal"} /></td>
                      <td><StatusBadge type={statusType(c.status)} label={c.status || "New"} /></td>
                      <td>{c.assigned_to || "Unassigned"}</td>
                      <td>{c.escalation_level || "normal"}</td>
                      <td>{(c.created_at || "").slice(0, 16)}</td>
                      <td><Btn size="sm" variant="light" onClick={(e) => { e.stopPropagation(); setSelected(c); }}>View</Btn></td>
                    </tr>
                  ))}
                  {!items.length && <tr><td colSpan={10} style={{ color: T.muted, padding: 24 }}>No cases found.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
        {selected && (
          <>
            <div className="drawer-overlay" onClick={() => setSelected(null)} />
            <div className="drawer-panel">
              <div style={{ background: "linear-gradient(135deg,#2D4A6B,#3A6080)", padding: "20px 24px", display: "flex", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,.55)" }}>{selected.case_reference}</div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>{selected.subject_name || selected.category}</div>
                </div>
                <button onClick={() => setSelected(null)} aria-label="Close drawer" style={{ background: "rgba(255,255,255,.1)", border: 0, width: 32, height: 32, borderRadius: 8 }}>
                  <Icon name="x" size={18} color="white" />
                </button>
              </div>
              <div style={{ padding: 24 }}>
                <StatusBadge type={statusType(selected.status)} label={selected.status || "New"} />
                <div style={{ marginTop: 18, display: "grid", gap: 10, fontSize: 13 }}>
                  <b>Requester</b>
                  <span>{selected.requester_name} · {selected.requester_phone}</span>
                  <b>Person Concerned / Subject</b>
                  <span>{selected.subject_name || selected.category}</span>
                  <b>Concern / Feedback</b>
                  <span>{selected.concern_summary || selected.details}</span>
                  <b>Assigned To</b>
                  <span>{selected.assigned_to || "Unassigned"}</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
