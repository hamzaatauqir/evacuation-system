import { useState } from "react";
import { AdminLayout } from "../components/AdminLayout";
import { AdminKpiCard } from "../components/AdminKpiCard";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { Btn } from "../components/Btn";
import { Icon } from "../components/Icon";
import { T } from "../lib/tokens";
import { LEGAL_CASES, cap, type LegalCase } from "./admin-data";

export function AdminLegalCasesPage() {
  const [selected, setSelected] = useState<LegalCase | null>(null);
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
            <h1 style={{ fontSize: 20, fontWeight: 800, color: T.navy }}>Legal Cases</h1>
            <p style={{ fontSize: 12, color: T.muted, marginTop: 2 }}>
              {LEGAL_CASES.length} total cases
            </p>
          </div>
          <Btn variant="light" size="sm" icon="download">
            Export
          </Btn>
        </div>
        <div style={{ padding: "20px 24px" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))",
              gap: 12,
              marginBottom: 20,
            }}
          >
            <AdminKpiCard label="Total Cases" value={LEGAL_CASES.length} accent="#2563eb" icon="scale" />
            <AdminKpiCard
              label="Pending"
              value={LEGAL_CASES.filter((c) => c.status === "pending").length}
              accent="#92400e"
              icon="clock"
              iconBg="#fffbeb"
            />
            <AdminKpiCard
              label="Urgent"
              value={LEGAL_CASES.filter((c) => c.priority === "urgent").length}
              accent={T.error}
              icon="alert"
              iconBg={T.errorBg}
            />
            <AdminKpiCard
              label="Resolved"
              value={LEGAL_CASES.filter((c) => c.status === "resolved").length}
              accent={T.successFg}
              icon="check"
              iconBg={T.successBg}
            />
          </div>
          <Card pad={0} style={{ overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="a-table">
                <thead>
                  <tr>
                    <th>Case ID</th>
                    <th>Applicant</th>
                    <th>Case Type</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Assigned To</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {LEGAL_CASES.map((c) => (
                    <tr key={c.id} onClick={() => setSelected(c)}>
                      <td>
                        <span style={{ fontWeight: 700, fontSize: 12, color: "#2563eb" }}>{c.id}</span>
                      </td>
                      <td style={{ fontWeight: 600 }}>{c.name}</td>
                      <td style={{ fontSize: 12, color: T.muted }}>{c.type}</td>
                      <td>
                        <StatusBadge type={c.priority} label={cap(c.priority)} />
                      </td>
                      <td>
                        <StatusBadge type={c.status} label={cap(c.status)} />
                      </td>
                      <td
                        style={{
                          fontSize: 12,
                          color: c.assigned === "Unassigned" ? T.mutedLt : T.text,
                          fontStyle: c.assigned === "Unassigned" ? "italic" : "normal",
                        }}
                      >
                        {c.assigned}
                      </td>
                      <td style={{ fontSize: 11, color: T.mutedLt }}>{c.updated}</td>
                      <td>
                        <Btn
                          variant="light"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelected(c);
                          }}
                        >
                          View
                        </Btn>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
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
                  <div style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,.55)", marginBottom: 4 }}>
                    {selected.id}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>{selected.name}</div>
                  <div style={{ fontSize: 12, color: "rgba(255,255,255,.6)", marginTop: 2 }}>
                    {selected.type}
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
                  }}
                >
                  <Icon name="x" size={18} color="white" />
                </button>
              </div>
              <div style={{ padding: 24 }}>
                <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
                  <StatusBadge type={selected.status} label={cap(selected.status)} />
                  <StatusBadge type={selected.priority} label={`${cap(selected.priority)} Priority`} />
                </div>
                <div style={{ background: T.surfaceLow, borderRadius: 10, padding: 14, marginBottom: 16 }}>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: T.muted,
                      textTransform: "uppercase",
                      letterSpacing: ".04em",
                      marginBottom: 8,
                    }}
                  >
                    Case Details
                  </div>
                  {([
                    ["Case Type", selected.type],
                    ["Assigned To", selected.assigned],
                    ["Last Updated", selected.updated],
                  ] as [string, string][]).map(([l, v]) => (
                    <div key={l} style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <span style={{ fontSize: 12, color: T.muted }}>{l}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{v}</span>
                    </div>
                  ))}
                </div>
                <Btn variant="primary" fullWidth icon="check">
                  Mark Resolved
                </Btn>
              </div>
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
