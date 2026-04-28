import { useEffect, useMemo, useState } from "react";
import { AdminLayout } from "../components/AdminLayout";
import { AdminKpiCard } from "../components/AdminKpiCard";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { Btn } from "../components/Btn";
import { Icon } from "../components/Icon";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

const TABS = ["All", "Pending", "Accommodation", "Complaints", "Leaving Notice", "Assigned to Me", "Resolved"] as const;
type Tab = (typeof TABS)[number];
type NurseComplaint = {
  complaint_id?: string;
  nurse_reference_id?: string;
  nurse_full_name?: string;
  passport_number?: string;
  category?: string;
  complaint_category?: string;
  priority?: string;
  status?: string;
  complaint_status?: string;
  assigned_to_name?: string;
  assigned_to_username?: string;
  created_at?: string;
  updated_at?: string;
  subject?: string;
  description?: string;
  email_status?: string;
};
type SummaryTotals = {
  registrations?: number;
  pending_registrations?: number;
  accommodation_requests?: number;
  open_complaints?: number;
  leave_notices?: number;
  current_accommodation_related?: number;
};

function cap(v: string = "") {
  return v ? v.charAt(0).toUpperCase() + v.slice(1) : "";
}
function toStatus(v?: string) {
  const s = (v || "").toLowerCase();
  if (s.includes("resolved") || s.includes("closed")) return "resolved";
  if (s.includes("assign")) return "assigned";
  if (s.includes("progress") || s.includes("seen")) return "processing";
  return "pending";
}
function toPriority(v?: string) {
  const p = (v || "").toLowerCase();
  if (p.includes("urgent")) return "urgent";
  if (p.includes("important") || p.includes("high")) return "high";
  if (p.includes("low")) return "low";
  return "medium";
}

export function AdminNursesPage() {
  const [tab, setTab] = useState<Tab>("All");
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterPriority, setFilterPriority] = useState("");
  const [selected, setSelected] = useState<NurseComplaint | null>(null);
  const [remark, setRemark] = useState("");
  const [rows, setRows] = useState<NurseComplaint[]>([]);
  const [totals, setTotals] = useState<SummaryTotals>({});
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const [s, c] = await Promise.all([
          api.get<{ success?: boolean; totals?: SummaryTotals; error?: string }>("/api/admin/nurses/summary"),
          api.get<{ success?: boolean; items?: NurseComplaint[]; error?: string }>("/api/admin/nurses/complaints"),
        ]);
        if (!live) return;
        setTotals(s.totals || {});
        setRows(c.items || []);
        setError(s.error || c.error || "");
      } catch (e) {
        if (!live) return;
        setRows([]);
        setError((e as Error).message || "Failed to load admin nurses data.");
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const tabCounts: Record<Tab, number> = useMemo(
    () => ({
      All: rows.length,
      Pending: rows.filter((n) => toStatus(n.status || n.complaint_status) === "pending").length,
      Accommodation: 0,
      Complaints: rows.length,
      "Leaving Notice": 0,
      "Assigned to Me": rows.filter((n) => (n.assigned_to_name || n.assigned_to_username || "").trim()).length,
      Resolved: rows.filter((n) => toStatus(n.status || n.complaint_status) === "resolved").length,
    }),
    [rows]
  );

  const filtered = useMemo(() => {
    return rows.filter((n) => {
      const q = search.toLowerCase();
      const matchSearch =
        !q ||
        (n.nurse_full_name || "").toLowerCase().includes(q) ||
        (n.passport_number || "").toLowerCase().includes(q) ||
        (n.nurse_reference_id || "").toLowerCase().includes(q) ||
        (n.complaint_id || "").toLowerCase().includes(q) ||
        (n.subject || "").toLowerCase().includes(q);
      const status = toStatus(n.status || n.complaint_status);
      const priority = toPriority(n.priority);
      const matchStatus = !filterStatus || status === filterStatus;
      const matchPriority = !filterPriority || priority === filterPriority;
      const matchTab =
        tab === "All" ||
        (tab === "Pending" && status === "pending") ||
        (tab === "Complaints" && true) ||
        (tab === "Assigned to Me" && !!(n.assigned_to_name || n.assigned_to_username)) ||
        (tab === "Resolved" && status === "resolved");
      return matchSearch && matchStatus && matchPriority && matchTab;
    });
  }, [rows, tab, search, filterStatus, filterPriority]);

  return (
    <AdminLayout>
      <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column" }} className="fade-in">
        {/* Subheader */}
        <div
          style={{
            background: T.surface,
            borderBottom: `1px solid ${T.borderLt}`,
            padding: "16px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, color: T.navy }}>Nurses Management</h1>
            <p style={{ fontSize: 12, color: T.muted, marginTop: 2 }}>{rows.length} total complaint records</p>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <Btn variant="light" size="sm" icon="download">
              Export
            </Btn>
          </div>
        </div>

        <div style={{ padding: "20px 24px", flex: 1 }}>
          {/* KPI row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))",
              gap: 12,
              marginBottom: 20,
            }}
          >
            <AdminKpiCard label="Total Nurses" value={totals.registrations || 0} accent={T.navy} icon="users" />
            <AdminKpiCard
              label="Pending"
              value={totals.pending_registrations || 0}
              accent="#92400e"
              icon="clock"
              iconBg="#fffbeb"
            />
            <AdminKpiCard
              label="Accommodation"
              value={totals.accommodation_requests || 0}
              accent="#0369a1"
              icon="home"
              iconBg="#f0f9ff"
            />
            <AdminKpiCard
              label="Open Complaints"
              value={totals.open_complaints || 0}
              accent={T.error}
              icon="alert"
              iconBg={T.errorBg}
            />
            <AdminKpiCard
              label="Leave Notices"
              value={totals.leave_notices || 0}
              accent={T.successFg}
              icon="check"
              iconBg={T.successBg}
            />
          </div>

          {/* Tabs */}
          <div className="tab-bar">
            {TABS.map((t) => (
              <button
                key={t}
                className={`tab-item${tab === t ? " active" : ""}`}
                onClick={() => setTab(t)}
              >
                {t}
                <span className="tab-badge">{tabCounts[t] || 0}</span>
              </button>
            ))}
          </div>

          {/* Search + filters */}
          <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 220px", position: "relative" }}>
              <div
                style={{
                  position: "absolute",
                  left: 10,
                  top: "50%",
                  transform: "translateY(-50%)",
                  pointerEvents: "none",
                }}
              >
                <Icon name="search" size={15} color={T.mutedLt} />
              </div>
              <input
                className="f-input"
                placeholder="Search name, passport, civil ID, hospital…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: 34, fontSize: 13 }}
              />
            </div>
            <select
              className="f-input"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              style={{ width: 150, fontSize: 13 }}
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="assigned">Assigned</option>
              <option value="resolved">Resolved</option>
            </select>
            <select
              className="f-input"
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
              style={{ width: 150, fontSize: 13 }}
            >
              <option value="">All Priority</option>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          {/* Table */}
          <Card pad={0} style={{ overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="a-table">
                <thead>
                  <tr>
                    <th>Ref No.</th>
                    <th>Nurse Name</th>
                    <th>Passport / Civil ID</th>
                    <th>Hospital</th>
                    <th>Type</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Assigned To</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={10} style={{ textAlign: "center", padding: "40px 0", color: T.muted, fontSize: 13 }}>
                        No records found
                      </td>
                    </tr>
                  ) : (
                    filtered.map((n, idx) => (
                      <tr key={n.complaint_id || idx} onClick={() => setSelected(n)}>
                        <td>
                          <span style={{ fontWeight: 700, fontSize: 12, color: T.navy }}>{n.complaint_id || "-"}</span>
                        </td>
                        <td>
                          <span style={{ fontWeight: 600, color: T.text }}>{n.nurse_full_name || "-"}</span>
                        </td>
                        <td>
                          <div style={{ fontSize: 12 }}>
                            <div style={{ fontWeight: 600 }}>{n.passport_number || "-"}</div>
                            <div style={{ color: T.mutedLt }}>{n.nurse_reference_id || "-"}</div>
                          </div>
                        </td>
                        <td>
                          <span style={{ fontSize: 12 }}>{n.subject || "-"}</span>
                        </td>
                        <td>
                          <span style={{ fontSize: 12, color: T.muted }}>{n.category || n.complaint_category || "-"}</span>
                        </td>
                        <td>
                          <StatusBadge type={toPriority(n.priority)} label={cap(toPriority(n.priority))} />
                        </td>
                        <td>
                          <StatusBadge type={toStatus(n.status || n.complaint_status)} label={cap(toStatus(n.status || n.complaint_status))} />
                        </td>
                        <td>
                          <span
                            style={{
                              fontSize: 12,
                              color: (n.assigned_to_name || n.assigned_to_username) ? T.text : T.mutedLt,
                              fontStyle: (n.assigned_to_name || n.assigned_to_username) ? "normal" : "italic",
                            }}
                          >
                            {n.assigned_to_name || n.assigned_to_username || "Unassigned"}
                          </span>
                        </td>
                        <td style={{ fontSize: 11, color: T.mutedLt }}>{n.updated_at || n.created_at || "-"}</td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <div style={{ display: "flex", gap: 6 }}>
                            <Btn variant="light" size="sm" onClick={() => setSelected(n)}>
                              View
                            </Btn>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        {/* Detail Drawer */}
        {selected && (
          <>
            <div className="drawer-overlay" onClick={() => setSelected(null)} />
            <div className="drawer-panel">
              <div
                style={{
                  background: "linear-gradient(135deg,#2D4A6B,#3A6080)",
                  padding: "20px 24px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: "rgba(255,255,255,.55)",
                      letterSpacing: ".04em",
                      marginBottom: 4,
                    }}
                  >
                    {selected.complaint_id || "-"}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>{selected.nurse_full_name || "-"}</div>
                  <div style={{ fontSize: 12, color: "rgba(255,255,255,.6)", marginTop: 2 }}>
                    {(selected.category || selected.complaint_category || "-")} · {(selected.subject || "-")}
                  </div>
                </div>
                <button
                  onClick={() => setSelected(null)}
                  aria-label="Close drawer"
                  style={{
                    background: "rgba(255,255,255,.1)",
                    border: "none",
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                >
                  <Icon name="x" size={18} color="white" />
                </button>
              </div>
              <div style={{ height: 3, background: `linear-gradient(90deg,${T.green},#106e09)` }} />

              <div style={{ padding: 24 }}>
                <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
                  <StatusBadge type={toStatus(selected.status || selected.complaint_status)} label={cap(toStatus(selected.status || selected.complaint_status))} />
                  <StatusBadge type={toPriority(selected.priority)} label={`${cap(toPriority(selected.priority))} Priority`} />
                </div>

                <div style={{ background: T.surfaceLow, borderRadius: 10, padding: 16, marginBottom: 16 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: T.muted,
                      textTransform: "uppercase",
                      letterSpacing: ".04em",
                      marginBottom: 12,
                    }}
                  >
                    Nurse Profile
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    {([
                      ["Passport", selected.passport_number || "-"],
                      ["Reference", selected.nurse_reference_id || "-"],
                      ["Category", selected.category || selected.complaint_category || "-"],
                      ["Email Status", selected.email_status || "Unverified"],
                      ["Priority", selected.priority || "-"],
                      ["Description", selected.description || "-"],
                    ] as [string, string][]).map(([l, v]) => (
                      <div key={l} style={{ gridColumn: l === "Description" ? "1/-1" : undefined }}>
                        <div style={{ fontSize: 11, color: T.muted, fontWeight: 600, marginBottom: 2 }}>{l}</div>
                        <div style={{ fontSize: 13, color: T.text, fontWeight: 600 }}>{v}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: T.muted,
                      textTransform: "uppercase",
                      letterSpacing: ".04em",
                      marginBottom: 8,
                    }}
                  >
                    Assignment
                  </div>
                  <select className="f-input" defaultValue={selected.assigned_to_name || selected.assigned_to_username || "Unassigned"} style={{ fontSize: 13 }}>
                    <option>Officer Khalid</option>
                    <option>Officer Ayesha</option>
                    <option>Officer Hira</option>
                    <option>Officer Raza</option>
                    <option>Unassigned</option>
                  </select>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: T.muted,
                      textTransform: "uppercase",
                      letterSpacing: ".04em",
                      marginBottom: 8,
                    }}
                  >
                    Update Status
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {(["pending", "processing", "assigned", "resolved"] as const).map((s) => (
                      <button
                        key={s}
                        style={{
                          padding: "6px 14px",
                          borderRadius: 20,
                          border: `1.5px solid ${toStatus(selected.status || selected.complaint_status) === s ? T.navy : T.borderLt}`,
                          background: toStatus(selected.status || selected.complaint_status) === s ? T.navy : "transparent",
                          color: toStatus(selected.status || selected.complaint_status) === s ? "#fff" : T.muted,
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        {cap(s)}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: T.muted,
                      textTransform: "uppercase",
                      letterSpacing: ".04em",
                      marginBottom: 8,
                    }}
                  >
                    Internal Remark
                  </div>
                  <textarea
                    className="f-input"
                    rows={3}
                    placeholder="Add an internal note or update…"
                    value={remark}
                    onChange={(e) => setRemark(e.target.value)}
                  />
                </div>

                <div style={{ marginBottom: 20 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: T.muted,
                      textTransform: "uppercase",
                      letterSpacing: ".04em",
                      marginBottom: 10,
                    }}
                  >
                    Activity Timeline
                  </div>
                  {[
                    { label: "Case registered", sub: "Submitted via portal", time: "26 Apr, 9:14 AM" },
                    {
                      label: "Assigned to " + (selected.assigned_to_name || selected.assigned_to_username || "Unassigned"),
                      sub: "Automatic assignment",
                      time: "26 Apr, 9:15 AM",
                    },
                    {
                      label: "Status: " + (selected.status || selected.complaint_status || "Submitted"),
                      sub: "Awaiting action",
                      time: (selected.updated_at || selected.created_at || "-") + ", 10:00 AM",
                    },
                  ].map((ev, i) => (
                    <div key={i} style={{ display: "flex", gap: 12, marginBottom: 12, alignItems: "flex-start" }}>
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          background: T.green,
                          marginTop: 4,
                          flexShrink: 0,
                        }}
                      />
                      <div
                        style={{
                          flex: 1,
                          paddingBottom: 12,
                          borderBottom: i < 2 ? `1px solid ${T.borderLt}` : "none",
                        }}
                      >
                        <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{ev.label}</div>
                        <div style={{ fontSize: 11, color: T.muted }}>{ev.sub}</div>
                      </div>
                      <div style={{ fontSize: 11, color: T.mutedLt, flexShrink: 0 }}>{ev.time}</div>
                    </div>
                  ))}
                </div>

                <div style={{ display: "flex", gap: 10, paddingTop: 16, borderTop: `1px solid ${T.borderLt}` }}>
                  <Btn variant="primary" fullWidth icon="check">
                    Mark Resolved
                  </Btn>
                  <Btn variant="light" fullWidth>
                    Add Note
                  </Btn>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
