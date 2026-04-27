import { useState } from "react";
import { AdminLayout } from "../components/AdminLayout";
import { AdminKpiCard } from "../components/AdminKpiCard";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { Btn } from "../components/Btn";
import { Icon } from "../components/Icon";
import { NoticeCard } from "../components/NoticeCard";
import { T } from "../lib/tokens";
import { DEATH_CASES, cap, type DeathCase } from "./admin-data";

function docColor(status: DeathCase["docStatus"]) {
  if (status === "Complete") return { bg: T.successBg, fg: T.successFg };
  if (status === "In Progress") return { bg: T.infoBg, fg: T.infoFg };
  return { bg: T.warningBg, fg: T.warningFg };
}

export function AdminDeathCasesPage() {
  const [selected, setSelected] = useState<DeathCase | null>(null);
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
            <h1 style={{ fontSize: 20, fontWeight: 800, color: T.navy }}>Death Cases</h1>
            <p style={{ fontSize: 12, color: T.muted, marginTop: 2 }}>
              Handled with sensitivity and urgency
            </p>
          </div>
          <Btn variant="light" size="sm" icon="download">
            Export
          </Btn>
        </div>
        <div style={{ padding: "20px 24px" }}>
          <div style={{ marginBottom: 16 }}>
            <NoticeCard type="warning" title="Sensitive Cases">
              These cases require urgent attention and respectful handling. Ensure family contact is
              made promptly.
            </NoticeCard>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))",
              gap: 12,
              marginBottom: 20,
            }}
          >
            <AdminKpiCard label="Total Cases" value={DEATH_CASES.length} accent="#6b21a8" icon="heart" />
            <AdminKpiCard
              label="Pending"
              value={DEATH_CASES.filter((c) => c.status === "pending").length}
              accent="#92400e"
              icon="clock"
              iconBg="#fffbeb"
            />
            <AdminKpiCard
              label="Urgent"
              value={DEATH_CASES.filter((c) => c.priority === "urgent").length}
              accent={T.error}
              icon="alert"
              iconBg={T.errorBg}
            />
            <AdminKpiCard
              label="Resolved"
              value={DEATH_CASES.filter((c) => c.status === "resolved").length}
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
                    <th>Deceased Name</th>
                    <th>Family Contact</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Docs Status</th>
                    <th>Assigned</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {DEATH_CASES.map((c) => {
                    const dc = docColor(c.docStatus);
                    return (
                      <tr key={c.id} onClick={() => setSelected(c)}>
                        <td>
                          <span style={{ fontWeight: 700, fontSize: 12, color: "#6b21a8" }}>{c.id}</span>
                        </td>
                        <td style={{ fontWeight: 600 }}>{c.name}</td>
                        <td style={{ fontSize: 12, color: T.muted }}>{c.contact}</td>
                        <td>
                          <StatusBadge type={c.priority} label={cap(c.priority)} />
                        </td>
                        <td>
                          <StatusBadge type={c.status} label={cap(c.status)} />
                        </td>
                        <td>
                          <span
                            style={{
                              fontSize: 12,
                              padding: "2px 8px",
                              borderRadius: 4,
                              background: dc.bg,
                              color: dc.fg,
                              fontWeight: 600,
                            }}
                          >
                            {c.docStatus}
                          </span>
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
                    );
                  })}
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
                    Death Case — {selected.contact}
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
                  {([
                    ["Documentation", selected.docStatus],
                    ["Assigned To", selected.assigned],
                    ["Last Updated", selected.updated],
                  ] as [string, string][]).map(([l, v]) => (
                    <div key={l} style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <span style={{ fontSize: 12, color: T.muted }}>{l}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{v}</span>
                    </div>
                  ))}
                </div>
                <div style={{ marginBottom: 16 }}>
                  <NoticeCard type="info">
                    Ensure family has been contacted and is informed of the process.
                  </NoticeCard>
                </div>
                <div style={{ display: "flex", gap: 10 }}>
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
