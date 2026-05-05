import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AdminLayout } from "../components/AdminLayout";
import { AdminKpiCard } from "../components/AdminKpiCard";
import { Btn } from "../components/Btn";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

type OnboardingRow = {
  nurse_id: number;
  reference_id?: string;
  name?: string;
  passport_masked?: string;
  passport_number?: string;
  mobile?: string;
  whatsapp?: string;
  email?: string;
  mton_number?: string;
  arrival_batch?: string;
  current_stage_code?: string;
  current_stage_name?: string;
  issue_status?: string;
  nurse_note?: string;
  progress_percent?: number;
  completed_steps_count?: number;
  total_steps_count?: number;
  help_needed?: boolean;
  last_updated_at?: string;
  no_update_days?: number;
  has_progress_row?: boolean;
  help_request_status?: string;
  help_request_id?: number;
};

type StepInfo = {
  step_code: string;
  step_name: string;
  sort_order?: number;
};

type Kpis = {
  total_tracked_nurses?: number;
  need_embassy_help?: number;
  waiting_pending?: number;
  no_update_7_days?: number;
  no_update_14_days?: number;
  salary_pending?: number;
  civil_id_pending?: number;
  medical_license_pending?: number;
};

type ListResponse = {
  success?: boolean;
  items?: OnboardingRow[];
  rows?: OnboardingRow[];
  kpis?: Kpis;
  steps?: StepInfo[];
  error?: string;
};

type DetailResponse = {
  success?: boolean;
  nurse?: {
    id: number;
    reference_id?: string;
    full_name?: string;
    father_name?: string;
    passport_number?: string;
    mobile?: string;
    whatsapp?: string;
    email?: string;
    mton_number?: string;
    batch_number?: string;
  };
  progress?: {
    current_stage_code?: string;
    issue_status?: string;
    nurse_note?: string;
    progress_percent?: number;
    completed_steps_count?: number;
    total_steps_count?: number;
    help_needed?: number | boolean;
    last_updated_at?: string;
    updated_by?: string;
    updated_by_role?: string;
  };
  steps?: Array<{
    step_code: string;
    step_name: string;
    short_guidance?: string;
    sort_order?: number;
    state?: "completed" | "current" | "upcoming" | "not_started";
  }>;
  help_request?: {
    id?: number;
    status?: string;
    issue_note?: string;
    assigned_to?: string;
    assigned_role?: string;
    created_at?: string;
    updated_at?: string;
    resolved_at?: string;
    escalation_note?: string;
  } | null;
  audit?: Array<{
    id: number;
    event_type?: string;
    old_stage_code?: string;
    new_stage_code?: string;
    old_issue_status?: string;
    new_issue_status?: string;
    old_note?: string;
    new_note?: string;
    actor?: string;
    actor_role?: string;
    created_at?: string;
  }>;
  error?: string;
};

function prettifyHelpStatus(status?: string) {
  if (!status) return "";
  return status
    .toLowerCase()
    .split("_")
    .map((p) => (p ? p.charAt(0).toUpperCase() + p.slice(1) : p))
    .join(" ");
}

function issueBadgeType(status?: string): "resolved" | "pending" | "info" | "assigned" | "processing" {
  const s = (status || "").toUpperCase();
  if (s === "NO_ISSUE") return "resolved";
  if (s === "WAITING") return "info";
  if (s === "NEED_HELP") return "pending";
  return "info";
}

function buildListQueryString(params: Record<string, string>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) q.set(k, v);
  }
  return q.toString();
}

export function AdminNurseOnboardingPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<OnboardingRow[]>([]);
  const [steps, setSteps] = useState<StepInfo[]>([]);
  const [kpis, setKpis] = useState<Kpis>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [issueFilter, setIssueFilter] = useState("");
  const [helpFilter, setHelpFilter] = useState("");
  const [noUpdateDays, setNoUpdateDays] = useState("");

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailData, setDetailData] = useState<DetailResponse | null>(null);
  const [detailSelectedStage, setDetailSelectedStage] = useState("");
  const [detailIssueStatus, setDetailIssueStatus] = useState("NO_ISSUE");
  const [detailAdminNote, setDetailAdminNote] = useState("");
  const [detailBusy, setDetailBusy] = useState(false);
  const [detailFlash, setDetailFlash] = useState("");

  const [copiedMessageNurseId, setCopiedMessageNurseId] = useState<number | null>(null);

  async function loadList() {
    setLoading(true);
    setError("");
    try {
      const qs = buildListQueryString({
        search,
        stage_code: stageFilter,
        issue_status: issueFilter,
        help_needed: helpFilter,
        no_update_days: noUpdateDays,
      });
      const res = await api.get<ListResponse>(
        `/api/admin/nurses/onboarding/list${qs ? `?${qs}` : ""}`
      );
      if (!res?.success) {
        throw new Error(res?.error || "Could not load MOH onboarding list.");
      }
      setRows(res.items || res.rows || []);
      setKpis(res.kpis || {});
      setSteps(res.steps || []);
    } catch (err) {
      setRows([]);
      setKpis({});
      setError((err as Error).message || "Could not load MOH onboarding list.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => rows, [rows]);

  async function openDetail(nurseId: number) {
    setDetailOpen(true);
    setDetailLoading(true);
    setDetailError("");
    setDetailFlash("");
    setDetailData(null);
    try {
      const res = await api.get<DetailResponse>(
        `/api/admin/nurses/onboarding/detail?nurse_id=${encodeURIComponent(String(nurseId))}`
      );
      if (!res?.success) {
        throw new Error(res?.error || "Could not load onboarding detail.");
      }
      setDetailData(res);
      setDetailSelectedStage(res.progress?.current_stage_code || "");
      setDetailIssueStatus((res.progress?.issue_status as string) || "NO_ISSUE");
      setDetailAdminNote("");
    } catch (err) {
      setDetailError((err as Error).message || "Could not load onboarding detail.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function submitAdminUpdate() {
    if (!detailData?.nurse?.id) return;
    if (!detailSelectedStage) {
      setDetailError("Please select a current stage.");
      return;
    }
    setDetailBusy(true);
    setDetailError("");
    setDetailFlash("");
    try {
      const res = await api.post<{ success?: boolean; message?: string; error?: string }>(
        "/api/admin/nurses/onboarding/update",
        {
          nurse_id: detailData.nurse.id,
          current_stage_code: detailSelectedStage,
          issue_status: detailIssueStatus,
          admin_note: detailAdminNote,
        }
      );
      if (!res?.success) {
        throw new Error(res?.error || "Update could not be saved.");
      }
      setDetailFlash(res.message || "Onboarding status updated.");
      setDetailAdminNote("");
      await openDetail(detailData.nurse.id);
      await loadList();
    } catch (err) {
      setDetailError((err as Error).message || "Update could not be saved.");
    } finally {
      setDetailBusy(false);
    }
  }

  async function copyRequestUpdateMessage(nurseId: number) {
    setCopiedMessageNurseId(null);
    try {
      const res = await api.post<{ success?: boolean; message_text?: string; whatsapp?: string; error?: string }>(
        "/api/admin/nurses/onboarding/request-update",
        { nurse_id: nurseId }
      );
      if (!res?.success) {
        throw new Error(res?.error || "Could not generate request-update message.");
      }
      const text = res.message_text || "";
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setCopiedMessageNurseId(nurseId);
        setTimeout(() => setCopiedMessageNurseId((cur) => (cur === nurseId ? null : cur)), 2500);
      } else {
        window.prompt("Copy this request-update message:", text);
      }
    } catch (err) {
      setError((err as Error).message || "Could not copy request-update message.");
    }
  }

  function downloadCsv() {
    const qs = buildListQueryString({
      search,
      stage_code: stageFilter,
      issue_status: issueFilter,
      help_needed: helpFilter,
      no_update_days: noUpdateDays,
    });
    window.location.href = `/api/admin/nurses/onboarding/export.csv${qs ? `?${qs}` : ""}`;
  }

  return (
    <AdminLayout>
      <div style={{ flex: 1, overflow: "auto", padding: 24 }} className="fade-in">
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
            <h1 style={{ fontSize: 22, fontWeight: 800, color: T.navy }}>MOH Onboarding Tracker</h1>
            <p style={{ marginTop: 4, color: T.muted, fontSize: 13 }}>
              Monitor newly arrived nurses, current MOH settlement stage, and help-needed cases.
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <Btn variant="light" onClick={() => navigate("/admin/nurses")}>Back to Nurses</Btn>
            <Btn variant="light" onClick={downloadCsv}>Export CSV</Btn>
            <Btn variant="navy" onClick={() => void loadList()}>Refresh</Btn>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))",
            gap: 12,
            marginBottom: 16,
          }}
        >
          <AdminKpiCard label="Total tracked nurses" value={kpis.total_tracked_nurses || 0} accent={T.navy} icon="users" />
          <AdminKpiCard label="Need Embassy Help" value={kpis.need_embassy_help || 0} accent="#b91c1c" icon="alert" />
          <AdminKpiCard label="Waiting / Pending" value={kpis.waiting_pending || 0} accent="#92400e" icon="clock" />
          <AdminKpiCard label="No Update 7 Days" value={kpis.no_update_7_days || 0} accent="#92400e" icon="clock" />
          <AdminKpiCard label="No Update 14 Days" value={kpis.no_update_14_days || 0} accent="#92400e" icon="clock" />
          <AdminKpiCard label="Salary Pending" value={kpis.salary_pending || 0} accent="#1f2937" icon="note" />
          <AdminKpiCard label="Civil ID Pending" value={kpis.civil_id_pending || 0} accent="#1f2937" icon="note" />
          <AdminKpiCard label="Medical License Pending" value={kpis.medical_license_pending || 0} accent="#1f2937" icon="note" />
        </div>

        <Card style={{ marginBottom: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 10 }}>
            <label style={{ color: T.muted, fontSize: 12 }}>
              Search
              <input
                className="f-input"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Name, passport, reference, MTON"
                onKeyDown={(e) => {
                  if (e.key === "Enter") void loadList();
                }}
              />
            </label>
            <label style={{ color: T.muted, fontSize: 12 }}>
              Stage
              <select className="f-input" value={stageFilter} onChange={(e) => setStageFilter(e.target.value)}>
                <option value="">All stages</option>
                {steps.map((s) => (
                  <option key={s.step_code} value={s.step_code}>
                    {(s.sort_order || 0)}. {s.step_name}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ color: T.muted, fontSize: 12 }}>
              Issue status
              <select className="f-input" value={issueFilter} onChange={(e) => setIssueFilter(e.target.value)}>
                <option value="">All</option>
                <option value="NO_ISSUE">No issue</option>
                <option value="WAITING">Waiting / pending</option>
                <option value="NEED_HELP">Need Embassy help</option>
              </select>
            </label>
            <label style={{ color: T.muted, fontSize: 12 }}>
              Help needed
              <select className="f-input" value={helpFilter} onChange={(e) => setHelpFilter(e.target.value)}>
                <option value="">All</option>
                <option value="1">Yes</option>
                <option value="0">No</option>
              </select>
            </label>
            <label style={{ color: T.muted, fontSize: 12 }}>
              No update for (days)
              <input
                className="f-input"
                value={noUpdateDays}
                inputMode="numeric"
                onChange={(e) => setNoUpdateDays(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="e.g. 7 or 14"
              />
            </label>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
              <Btn variant="navy" onClick={() => void loadList()}>Apply</Btn>
              <Btn
                variant="light"
                onClick={() => {
                  setSearch("");
                  setStageFilter("");
                  setIssueFilter("");
                  setHelpFilter("");
                  setNoUpdateDays("");
                  setTimeout(() => void loadList(), 0);
                }}
              >
                Clear
              </Btn>
            </div>
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
            <div style={{ padding: 24, color: T.muted }}>Loading nurses…</div>
          ) : filtered.length ? (
            <div style={{ overflowX: "auto" }}>
              <table className="a-table">
                <thead>
                  <tr>
                    <th>Nurse</th>
                    <th>MTON</th>
                    <th>Mobile</th>
                    <th>Current stage</th>
                    <th>Issue</th>
                    <th>Progress</th>
                    <th>Last update</th>
                    <th>Help</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.nurse_id}>
                      <td>
                        <div style={{ display: "grid", gap: 4 }}>
                          <strong style={{ color: T.navy }}>{row.name || "Nurse"}</strong>
                          <span style={{ fontSize: 12, color: T.muted }}>
                            {row.reference_id || "—"} | {row.passport_masked || "—"}
                          </span>
                          {row.arrival_batch ? (
                            <span style={{ fontSize: 12, color: T.muted }}>Batch: {row.arrival_batch}</span>
                          ) : null}
                        </div>
                      </td>
                      <td>{row.mton_number || "—"}</td>
                      <td>
                        <div style={{ display: "grid", gap: 2, fontSize: 12 }}>
                          <span>{row.mobile || "—"}</span>
                          {row.whatsapp && row.whatsapp !== row.mobile ? (
                            <span style={{ color: T.muted }}>WA: {row.whatsapp}</span>
                          ) : null}
                        </div>
                      </td>
                      <td>{row.current_stage_name || (row.has_progress_row ? "—" : "Not started")}</td>
                      <td>
                        <StatusBadge type={issueBadgeType(row.issue_status)} label={prettifyHelpStatus(row.issue_status) || "—"} />
                      </td>
                      <td>
                        <div style={{ minWidth: 120 }}>
                          <div style={{ height: 6, background: "#e2e8f0", borderRadius: 999, overflow: "hidden" }}>
                            <div
                              style={{
                                width: `${Math.min(100, Math.max(0, row.progress_percent || 0))}%`,
                                height: "100%",
                                background: "#2D4A6B",
                              }}
                            />
                          </div>
                          <div style={{ fontSize: 11, color: T.muted, marginTop: 4 }}>
                            {row.completed_steps_count || 0} of {row.total_steps_count || 17}
                            {" "}({(row.progress_percent || 0).toFixed(0)}%)
                          </div>
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "grid", gap: 2, fontSize: 12 }}>
                          <span>{row.last_updated_at || "—"}</span>
                          {row.has_progress_row && (row.no_update_days || 0) > 0 ? (
                            <span style={{ color: T.muted }}>{row.no_update_days} day(s) ago</span>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        {row.help_needed || row.help_request_status ? (
                          <StatusBadge type={row.help_needed ? "pending" : "info"} label={prettifyHelpStatus(row.help_request_status) || "Help needed"} />
                        ) : (
                          <span style={{ color: T.muted }}>—</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          <Btn variant="light" size="sm" onClick={() => void openDetail(row.nurse_id)}>
                            View detail
                          </Btn>
                          <Btn variant="light" size="sm" onClick={() => void copyRequestUpdateMessage(row.nurse_id)}>
                            {copiedMessageNurseId === row.nurse_id ? "Copied!" : "Copy update message"}
                          </Btn>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 24, color: T.muted }}>No nurses match these filters.</div>
          )}
        </Card>

        {detailOpen ? (
          <div
            role="dialog"
            aria-modal="true"
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(15, 23, 42, 0.45)",
              zIndex: 200,
              display: "flex",
              justifyContent: "flex-end",
            }}
            onClick={() => setDetailOpen(false)}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                width: "min(640px, 100%)",
                background: "#fff",
                height: "100%",
                overflowY: "auto",
                padding: 24,
                boxShadow: "-8px 0 24px rgba(15,23,42,0.18)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h2 style={{ fontSize: 18, fontWeight: 800, color: T.navy, margin: 0 }}>MOH Onboarding Detail</h2>
                <Btn variant="light" size="sm" onClick={() => setDetailOpen(false)}>Close</Btn>
              </div>

              {detailLoading ? (
                <div style={{ color: T.muted }}>Loading…</div>
              ) : detailError ? (
                <div
                  style={{
                    background: "#FEF2F1",
                    border: "1px solid #FECACA",
                    color: "#991B1B",
                    borderRadius: 10,
                    padding: 12,
                  }}
                >
                  {detailError}
                </div>
              ) : detailData ? (
                <div style={{ display: "grid", gap: 16 }}>
                  <Card>
                    <div style={{ display: "grid", gap: 4 }}>
                      <strong style={{ color: T.navy }}>{detailData.nurse?.full_name || "Nurse"}</strong>
                      <span style={{ fontSize: 12, color: T.muted }}>
                        {detailData.nurse?.reference_id || "—"} | Passport: {detailData.nurse?.passport_number || "—"}
                      </span>
                      <span style={{ fontSize: 12, color: T.muted }}>
                        Mobile: {detailData.nurse?.mobile || "—"} | Email: {detailData.nurse?.email || "—"}
                      </span>
                      <span style={{ fontSize: 12, color: T.muted }}>
                        MTON: {detailData.nurse?.mton_number || "—"} | Batch: {detailData.nurse?.batch_number || "—"}
                      </span>
                    </div>
                  </Card>

                  <Card>
                    <h3 style={{ margin: 0, fontSize: 14, color: T.navy, marginBottom: 8 }}>Update on behalf of nurse</h3>
                    {detailFlash ? (
                      <div style={{ marginBottom: 8, background: "#f3fff4", color: "#166534", border: "1px solid #bbf7d0", borderRadius: 10, padding: 10, fontSize: 13 }}>
                        {detailFlash}
                      </div>
                    ) : null}
                    <label style={{ fontSize: 12, color: T.muted }}>
                      Current Stage
                      <select
                        className="f-input"
                        value={detailSelectedStage}
                        onChange={(e) => setDetailSelectedStage(e.target.value)}
                      >
                        <option value="">Select stage</option>
                        {(detailData.steps || []).map((s) => (
                          <option key={s.step_code} value={s.step_code}>
                            {(s.sort_order || 0)}. {s.step_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label style={{ fontSize: 12, color: T.muted, marginTop: 8 }}>
                      Issue status
                      <select
                        className="f-input"
                        value={detailIssueStatus}
                        onChange={(e) => setDetailIssueStatus(e.target.value)}
                      >
                        <option value="NO_ISSUE">No issue</option>
                        <option value="WAITING">Waiting / pending</option>
                        <option value="NEED_HELP">Need Embassy help</option>
                      </select>
                    </label>
                    <label style={{ fontSize: 12, color: T.muted, marginTop: 8 }}>
                      Admin note (appended to nurse note, optional)
                      <textarea
                        className="f-input"
                        rows={3}
                        value={detailAdminNote}
                        onChange={(e) => setDetailAdminNote(e.target.value)}
                        placeholder="Optional internal note (will be visible in audit trail)"
                      />
                    </label>
                    <div style={{ marginTop: 8 }}>
                      <Btn variant="primary" onClick={submitAdminUpdate} disabled={detailBusy}>
                        {detailBusy ? "Updating..." : "Update Stage"}
                      </Btn>
                    </div>
                  </Card>

                  <Card>
                    <h3 style={{ margin: 0, fontSize: 14, color: T.navy, marginBottom: 8 }}>Stage progression</h3>
                    <div style={{ display: "grid", gap: 6 }}>
                      {(detailData.steps || []).map((s) => (
                        <div
                          key={s.step_code}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            padding: "6px 8px",
                            borderRadius: 8,
                            background:
                              s.state === "current" ? "#EEF4FB" : s.state === "completed" ? "#F0FFF4" : "#F8FAFC",
                            border: `1px solid ${s.state === "current" ? "#2D4A6B" : "#E3EBF0"}`,
                          }}
                        >
                          <span
                            style={{
                              width: 22,
                              textAlign: "center",
                              fontSize: 12,
                              color:
                                s.state === "completed"
                                  ? "#166534"
                                  : s.state === "current"
                                    ? "#2D4A6B"
                                    : "#94A3B8",
                            }}
                          >
                            {s.state === "completed" ? "✓" : (s.sort_order || 0)}
                          </span>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 13, color: "#1f2937" }}>{s.step_name}</div>
                            {s.state === "current" && s.short_guidance ? (
                              <div style={{ fontSize: 12, color: T.muted, marginTop: 2 }}>{s.short_guidance}</div>
                            ) : null}
                          </div>
                          <span style={{ fontSize: 11, color: T.muted, textTransform: "uppercase" }}>
                            {s.state || "—"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </Card>

                  {detailData.help_request ? (
                    <Card>
                      <h3 style={{ margin: 0, fontSize: 14, color: T.navy, marginBottom: 8 }}>Help request</h3>
                      <div style={{ display: "grid", gap: 4, fontSize: 13 }}>
                        <div><strong>Status:</strong> {prettifyHelpStatus(detailData.help_request.status) || "—"}</div>
                        <div><strong>Note:</strong> {detailData.help_request.issue_note || "—"}</div>
                        <div><strong>Assigned to:</strong> {detailData.help_request.assigned_to || "Nurses Welfare Desk"}</div>
                        <div><strong>Created:</strong> {detailData.help_request.created_at || "—"}</div>
                        {detailData.help_request.escalation_note ? (
                          <div><strong>Escalation:</strong> {detailData.help_request.escalation_note}</div>
                        ) : null}
                      </div>
                    </Card>
                  ) : null}

                  {detailData.audit && detailData.audit.length ? (
                    <Card>
                      <h3 style={{ margin: 0, fontSize: 14, color: T.navy, marginBottom: 8 }}>Audit log</h3>
                      <div style={{ display: "grid", gap: 6, fontSize: 12 }}>
                        {detailData.audit.slice(0, 25).map((a) => (
                          <div key={a.id} style={{ borderBottom: "1px solid #EEF2F7", paddingBottom: 6 }}>
                            <div style={{ color: T.navy, fontWeight: 600 }}>{a.event_type || "event"}</div>
                            <div style={{ color: T.muted }}>
                              {a.created_at || "—"} • {a.actor || "system"} ({a.actor_role || "—"})
                            </div>
                            {a.old_stage_code !== a.new_stage_code ? (
                              <div>Stage: {a.old_stage_code || "—"} → {a.new_stage_code || "—"}</div>
                            ) : null}
                            {a.old_issue_status !== a.new_issue_status ? (
                              <div>Issue: {a.old_issue_status || "—"} → {a.new_issue_status || "—"}</div>
                            ) : null}
                            {a.new_note && a.new_note !== a.old_note ? (
                              <div>Note: {a.new_note}</div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </Card>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </AdminLayout>
  );
}
