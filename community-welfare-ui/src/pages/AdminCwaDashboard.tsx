import { useNavigate } from "react-router-dom";
import { AdminLayout } from "../components/AdminLayout";
import { AdminKpiCard } from "../components/AdminKpiCard";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { Btn } from "../components/Btn";
import { Icon, type IconName } from "../components/Icon";
import { T } from "../lib/tokens";
import { NURSES, cap } from "./admin-data";

interface RecentRow {
  ref: string;
  type: string;
  name: string;
  status: "pending" | "processing" | "assigned" | "resolved";
  time: string;
}

const RECENT: RecentRow[] = [
  { ref: "CWR-2025-003", type: "Complaint", name: "Nadia Qureshi", status: "assigned", time: "2h ago" },
  { ref: "CWR-2025-002", type: "Accommodation", name: "Sana Rehman", status: "processing", time: "5h ago" },
  { ref: "LGL-2025-003", type: "Legal", name: "Tariq Mahmood", status: "assigned", time: "8h ago" },
  { ref: "CWR-2025-009", type: "Accommodation", name: "Amna Tariq", status: "assigned", time: "1d ago" },
  { ref: "DTH-2025-001", type: "Death Case", name: "Muhammad Nawaz", status: "processing", time: "1d ago" },
  { ref: "CWR-2025-007", type: "Complaint", name: "Samra Iqbal", status: "pending", time: "2d ago" },
];

interface ModuleTile {
  id: string;
  to: string;
  label: string;
  count: string;
  accent: string;
  icon: IconName;
}

const MODULES: ModuleTile[] = [
  { id: "nurses", to: "/admin/nurses", label: "Nurses", count: "12 active", accent: T.green, icon: "users" },
  { id: "legal", to: "/admin/legal-cases", label: "Legal Cases", count: "5 active", accent: "#2563eb", icon: "scale" },
  { id: "death", to: "/admin/death-cases", label: "Death Cases", count: "3 active", accent: "#6b21a8", icon: "heart" },
];

export function AdminCwaDashboard() {
  const navigate = useNavigate();
  return (
    <AdminLayout>
      <div style={{ flex: 1, overflow: "auto", padding: 24 }} className="fade-in">
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: T.navy }}>
            Community Welfare Overview
          </h1>
          <p style={{ fontSize: 13, color: T.muted, marginTop: 4 }}>
            Sunday, 27 April 2025 — Kuwait Time
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))",
            gap: 14,
            marginBottom: 24,
          }}
        >
          <AdminKpiCard label="Total Requests" value="47" sub="All time" accent={T.navy} icon="note" />
          <AdminKpiCard
            label="Pending Review"
            value="8"
            sub="Action needed"
            accent="#92400e"
            icon="clock"
            iconBg="#fffbeb"
          />
          <AdminKpiCard
            label="In Progress"
            value="6"
            sub="Being processed"
            accent={T.infoFg}
            icon="filter"
            iconBg={T.infoBg}
          />
          <AdminKpiCard
            label="Urgent Cases"
            value="3"
            sub="High priority"
            accent={T.error}
            icon="alert"
            iconBg={T.errorBg}
          />
          <AdminKpiCard
            label="Resolved This Week"
            value="11"
            sub="Closed cases"
            accent={T.successFg}
            icon="check"
            iconBg={T.successBg}
          />
          <AdminKpiCard
            label="Assigned to Me"
            value="5"
            sub="Officer Khalid"
            accent="#6b21a8"
            icon="user"
            iconBg="#f5f3ff"
          />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)",
            gap: 20,
          }}
        >
          <Card>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16,
              }}
            >
              <div style={{ fontSize: 15, fontWeight: 700, color: T.navy }}>Recent Activity</div>
              <Btn variant="light" size="sm" onClick={() => navigate("/admin/nurses")}>
                View All
              </Btn>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="a-table">
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Applicant</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {RECENT.map((r) => (
                    <tr key={r.ref}>
                      <td>
                        <span style={{ fontWeight: 700, fontSize: 12, color: T.navy }}>{r.ref}</span>
                      </td>
                      <td style={{ fontWeight: 600 }}>{r.name}</td>
                      <td>
                        <span style={{ fontSize: 12, color: T.muted }}>{r.type}</span>
                      </td>
                      <td>
                        <StatusBadge type={r.status} label={cap(r.status)} />
                      </td>
                      <td style={{ fontSize: 12, color: T.mutedLt }}>{r.time}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {MODULES.map((m) => (
              <button
                key={m.id}
                onClick={() => navigate(m.to)}
                style={{
                  background: T.surface,
                  borderRadius: 12,
                  padding: "16px 20px",
                  border: `1px solid ${T.borderLt}`,
                  boxShadow: "0 2px 8px rgba(0,33,71,.05)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  transition: "all .15s",
                  textAlign: "left",
                }}
              >
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    background: `${m.accent}16`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Icon name={m.icon} size={20} color={m.accent} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: T.navy }}>{m.label}</div>
                  <div style={{ fontSize: 12, color: T.muted }}>{m.count}</div>
                </div>
                <Icon name="chevron-r" size={16} color={T.border} />
              </button>
            ))}
            <Card style={{ borderTop: `3px solid ${T.error}` }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: T.error,
                  marginBottom: 10,
                  display: "flex",
                  gap: 6,
                  alignItems: "center",
                }}
              >
                <Icon name="alert" size={14} color={T.error} />
                Urgent Cases
              </div>
              {NURSES.filter((n) => n.priority === "urgent").map((n) => (
                <div
                  key={n.id}
                  style={{
                    padding: "8px 0",
                    borderBottom: `1px solid ${T.borderLt}`,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: T.navy }}>{n.name}</div>
                    <div style={{ fontSize: 11, color: T.muted }}>{n.type}</div>
                  </div>
                  <StatusBadge type="urgent" label="Urgent" />
                </div>
              ))}
            </Card>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
