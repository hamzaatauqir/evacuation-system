import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AdminLayout } from "../components/AdminLayout";
import { AdminKpiCard } from "../components/AdminKpiCard";
import { Btn } from "../components/Btn";
import { Card } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { Icon } from "../components/Icon";
import { T } from "../lib/tokens";
import { api } from "../lib/api";

type AccommodationRow = {
  nurse_id: number;
  roster_id?: number;
  nurse_reference?: string;
  name?: string;
  father_name?: string;
  mton_number?: string;
  passport_masked?: string;
  passport_number?: string;
  civil_id?: string;
  mobile?: string;
  whatsapp?: string;
  gender?: string;
  batch?: string;
  current_accommodation_type?: string;
  vendor_name?: string;
  facility_name?: string;
  room_no?: string;
  bed_no?: string;
  contract_start_date?: string;
  contract_end_date?: string;
  monthly_rate?: number | null;
  status?: string;
  request_status?: string;
  preference?: string;
  expected_shift_date?: string;
  leaving_notice_status?: string;
  last_updated?: string;
  no_update_days?: number;
  notes?: string;
  transfer_requested?: boolean;
  open_leave_notice?: boolean;
  has_vendor_assignment?: boolean;
  is_own_accommodation?: boolean;
  is_active_occupant?: boolean;
};

type Kpis = {
  total_records?: number;
  active_occupants?: number;
  pending_preference?: number;
  vendor_assigned?: number;
  transfer_requested?: number;
  leaving_notice_submitted?: number;
  own_accommodation?: number;
  no_update_7_days?: number;
};

type FilterOptions = {
  vendors?: string[];
  facilities?: string[];
  statuses?: string[];
  accommodation_types?: string[];
  preferences?: string[];
};

type ListResponse = {
  success?: boolean;
  items?: AccommodationRow[];
  kpis?: Kpis;
  filters?: FilterOptions;
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
    passport_masked?: string;
    civil_id?: string;
    mobile?: string;
    whatsapp?: string;
    email?: string;
    mton_number?: string;
    gender?: string;
    batch_number?: string;
    hospital?: string;
  };
  summary?: AccommodationRow;
  roster?: {
    id?: number;
    vendor_name?: string;
    facility_name?: string;
    room_number?: string;
    bed_number?: string;
    contract_start_date?: string;
    contract_end_date?: string;
    expected_shift_date?: string;
    current_status?: string;
    current_arrangement?: string;
    monthly_amount_kwd?: number | null;
    remarks?: string;
  } | null;
  actions?: Array<{
    id: number;
    actor_username?: string;
    action_type?: string;
    old_value?: string;
    new_value?: string;
    note?: string;
    created_at?: string;
  }>;
  accommodation_requests?: Array<{
    id?: number;
    current_accommodation_status?: string;
    requested_facility?: string;
    request_status?: string;
    admin_remarks?: string;
    reason_remarks?: string;
    created_at?: string;
    updated_at?: string;
  }>;
  leave_notices?: Array<{
    id?: number;
    current_facility?: string;
    intended_leaving_date?: string;
    reason?: string;
    notice_status?: string;
    admin_remarks?: string;
    new_stay_arrangement?: string;
    updated_at?: string;
  }>;
  complaints?: Array<{
    complaint_id?: string;
    category?: string;
    subject?: string;
    priority?: string;
    status?: string;
    created_at?: string;
    updated_at?: string;
  }>;
  error?: string;
  message?: string;
};

type FormState = {
  vendor_name: string;
  facility_name: string;
  room_no: string;
  bed_no: string;
  monthly_rate: string;
  contract_start_date: string;
  contract_end_date: string;
  expected_shift_date: string;
  status: string;
  notes: string;
};

type ViewKey =
  | "current"
  | "pending"
  | "agreements"
  | "transfer"
  | "leaving"
  | "directory"
  | "followup";

const VIEWS: Array<{ key: ViewKey; label: string }> = [
  { key: "current", label: "Current Roster" },
  { key: "pending", label: "New Arrivals / Pending Accommodation" },
  { key: "agreements", label: "Vendor Agreements" },
  { key: "transfer", label: "Shift / Transfer Requests" },
  { key: "leaving", label: "Leaving Notices" },
  { key: "directory", label: "Vendor Directory" },
  { key: "followup", label: "Export / WhatsApp Follow-up" },
];

const EMPTY_FORM: FormState = {
  vendor_name: "",
  facility_name: "",
  room_no: "",
  bed_no: "",
  monthly_rate: "",
  contract_start_date: "",
  contract_end_date: "",
  expected_shift_date: "",
  status: "",
  notes: "",
};

function buildQueryString(params: Record<string, string>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) q.set(k, v);
  }
  return q.toString();
}

function formatDateRange(start?: string, end?: string) {
  if (!start && !end) return "—";
  return [start || "—", end || "—"].join(" to ");
}

function formatRoomBed(row: AccommodationRow) {
  const room = row.room_no || "";
  const bed = row.bed_no || "";
  if (!room && !bed) return "—";
  return [room || "—", bed || "—"].join(" / ");
}

function formatUpdated(value?: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 16);
}

function statusType(status?: string): "pending" | "processing" | "resolved" | "closed" | "info" {
  const s = (status || "").toLowerCase();
  if (!s) return "info";
  if (s.includes("left") || s.includes("closed") || s.includes("inactive")) return "closed";
  if (s.includes("confirmed") || s.includes("active")) return "resolved";
  if (s.includes("pending") || s.includes("notice")) return "pending";
  if (s.includes("leave") || s.includes("transfer") || s.includes("review") || s.includes("shift")) return "processing";
  return "info";
}

function viewMatches(row: AccommodationRow, view: ViewKey) {
  if (view === "current") return Boolean(row.is_active_occupant || row.has_vendor_assignment || row.facility_name);
  if (view === "pending") return Boolean((row.request_status || "").trim() || (!row.vendor_name && !row.facility_name));
  if (view === "agreements") return Boolean(row.has_vendor_assignment);
  if (view === "transfer") return Boolean(row.transfer_requested);
  if (view === "leaving") return Boolean(row.open_leave_notice || row.leaving_notice_status);
  if (view === "directory") return Boolean(row.vendor_name);
  return true;
}

function detailToForm(detail: DetailResponse | null): FormState {
  const roster = detail?.roster || {};
  const summary = detail?.summary || {};
  return {
    vendor_name: (roster.vendor_name || summary.vendor_name || "").toString(),
    facility_name: (roster.facility_name || summary.facility_name || "").toString(),
    room_no: (roster.room_number || summary.room_no || "").toString(),
    bed_no: (roster.bed_number || summary.bed_no || "").toString(),
    monthly_rate:
      roster.monthly_amount_kwd == null || roster.monthly_amount_kwd === ""
        ? ""
        : String(roster.monthly_amount_kwd),
    contract_start_date: (roster.contract_start_date || summary.contract_start_date || "").toString(),
    contract_end_date: (roster.contract_end_date || summary.contract_end_date || "").toString(),
    expected_shift_date: (roster.expected_shift_date || summary.expected_shift_date || "").toString(),
    status: (roster.current_status || summary.status || "").toString(),
    notes: (roster.remarks || summary.notes || "").toString(),
  };
}

export function AdminNursesAccommodationPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<AccommodationRow[]>([]);
  const [kpis, setKpis] = useState<Kpis>({});
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accessDenied, setAccessDenied] = useState(false);
  const [flash, setFlash] = useState("");

  const [search, setSearch] = useState("");
  const [vendor, setVendor] = useState("");
  const [facility, setFacility] = useState("");
  const [status, setStatus] = useState("");
  const [accommodationType, setAccommodationType] = useState("");
  const [preference, setPreference] = useState("");
  const [mton, setMton] = useState("");
  const [noUpdateDays, setNoUpdateDays] = useState("");
  const [view, setView] = useState<ViewKey>("current");

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailData, setDetailData] = useState<DetailResponse | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  async function loadList(override?: Partial<Record<string, string>>) {
    setLoading(true);
    setError("");
    setAccessDenied(false);
    try {
      const qs = buildQueryString({
        search,
        vendor,
        facility,
        status,
        accommodation_type: accommodationType,
        preference,
        mton,
        no_update_days: noUpdateDays,
        ...(override || {}),
      });
      const res = await api.get<ListResponse>(
        `/api/admin/nurses/accommodation/list${qs ? `?${qs}` : ""}`
      );
      if (!res?.success) {
        throw new Error(res?.error || "Could not load accommodation roster.");
      }
      setRows(res.items || []);
      setKpis(res.kpis || {});
      setFilterOptions(res.filters || {});
    } catch (err) {
      const msg = (err as Error).message || "Could not load accommodation roster.";
      setRows([]);
      setKpis({});
      setFilterOptions({});
      setError(msg);
      setAccessDenied(/permission|access denied|unauthorized/i.test(msg));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleRows = useMemo(() => rows.filter((row) => viewMatches(row, view)), [rows, view]);

  const viewCounts = useMemo(() => {
    const counts: Record<ViewKey, number> = {
      current: 0,
      pending: 0,
      agreements: 0,
      transfer: 0,
      leaving: 0,
      directory: 0,
      followup: rows.length,
    };
    rows.forEach((row) => {
      if (viewMatches(row, "current")) counts.current += 1;
      if (viewMatches(row, "pending")) counts.pending += 1;
      if (viewMatches(row, "agreements")) counts.agreements += 1;
      if (viewMatches(row, "transfer")) counts.transfer += 1;
      if (viewMatches(row, "leaving")) counts.leaving += 1;
      if (viewMatches(row, "directory")) counts.directory += 1;
    });
    return counts;
  }, [rows]);

  async function openDetail(nurseId: number) {
    setDetailOpen(true);
    setDetailLoading(true);
    setDetailError("");
    try {
      const res = await api.get<DetailResponse>(
        `/api/admin/nurses/accommodation/detail?nurse_id=${encodeURIComponent(String(nurseId))}`
      );
      if (!res?.success) {
        throw new Error(res?.error || "Could not load nurse accommodation detail.");
      }
      setDetailData(res);
      setForm(detailToForm(res));
    } catch (err) {
      setDetailData(null);
      setForm(EMPTY_FORM);
      setDetailError((err as Error).message || "Could not load nurse accommodation detail.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function saveAccommodation() {
    if (!detailData?.nurse?.id) return;
    setSaving(true);
    setDetailError("");
    setFlash("");
    try {
      const res = await api.post<DetailResponse>("/api/admin/nurses/accommodation/update", {
        nurse_id: detailData.nurse.id,
        roster_id: detailData.roster?.id || detailData.summary?.roster_id || 0,
        vendor_name: form.vendor_name,
        facility_name: form.facility_name,
        room_no: form.room_no,
        bed_no: form.bed_no,
        monthly_rate: form.monthly_rate,
        contract_start_date: form.contract_start_date,
        contract_end_date: form.contract_end_date,
        expected_shift_date: form.expected_shift_date,
        status: form.status,
        notes: form.notes,
      });
      if (!res?.success) {
        throw new Error(res?.error || "Could not save accommodation details.");
      }
      setDetailData(res);
      setForm(detailToForm(res));
      setFlash(res.message || "Accommodation record updated.");
      await loadList();
    } catch (err) {
      setDetailError((err as Error).message || "Could not save accommodation details.");
    } finally {
      setSaving(false);
    }
  }

  async function copyMessage(nurseId: number, messageType: "REQUEST_PREFERENCE" | "SHIFT_NOTICE" | "TRANSFER_OPTION") {
    setFlash("");
    try {
      const res = await api.post<{ success?: boolean; message?: string; error?: string }>(
        "/api/admin/nurses/accommodation/request-update-message",
        { nurse_id: nurseId, message_type: messageType }
      );
      if (!res?.success || !res.message) {
        throw new Error(res?.error || "Could not generate follow-up message.");
      }
      await navigator.clipboard.writeText(res.message);
      setFlash("Follow-up message copied.");
    } catch (err) {
      setFlash((err as Error).message || "Could not copy follow-up message.");
    }
  }

  function exportCsv() {
    const qs = buildQueryString({
      search,
      vendor,
      facility,
      status,
      accommodation_type: accommodationType,
      preference,
      mton,
      no_update_days: noUpdateDays,
    });
    window.location.href = `/api/admin/nurses/accommodation/export.csv${qs ? `?${qs}` : ""}`;
  }

  return (
    <AdminLayout>
      <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column" }} className="fade-in">
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
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
              <button
                type="button"
                onClick={() => navigate("/admin/nurses")}
                style={{
                  border: `1px solid ${T.borderLt}`,
                  background: T.surfaceLow,
                  borderRadius: 8,
                  width: 34,
                  height: 34,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon name="chevron-l" size={16} color={T.navy} />
              </button>
              <div>
                <h1 style={{ fontSize: 20, fontWeight: 800, color: T.navy }}>
                  Accommodation / Hostel Roster
                </h1>
                <p style={{ fontSize: 12, color: T.muted, marginTop: 2 }}>
                  Track nurse accommodation, vendors, hostel movement, and transfer/leaving follow-up.
                </p>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <Btn variant="light" size="sm" onClick={() => navigate("/admin/nurses")}>
              Back to Nurses
            </Btn>
            <Btn variant="light" size="sm" icon="download" onClick={exportCsv}>
              Export CSV
            </Btn>
          </div>
        </div>

        <div style={{ padding: "20px 24px 28px", flex: 1 }}>
          {flash ? (
            <div
              style={{
                marginBottom: 14,
                padding: "10px 12px",
                borderRadius: 10,
                border: `1px solid ${T.borderLt}`,
                background: T.successBg,
                color: T.successFg,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {flash}
            </div>
          ) : null}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))",
              gap: 12,
              marginBottom: 20,
            }}
          >
            <AdminKpiCard label="Total Records" value={kpis.total_records || 0} accent={T.navy} icon="users" />
            <AdminKpiCard label="Active Occupants" value={kpis.active_occupants || 0} accent={T.green} icon="home" iconBg={T.greenLight} />
            <AdminKpiCard label="Pending Preference" value={kpis.pending_preference || 0} accent="#92400e" icon="clock" iconBg="#fffbeb" />
            <AdminKpiCard label="Vendor Assigned" value={kpis.vendor_assigned || 0} accent={T.infoFg} icon="building" iconBg={T.infoBg} />
            <AdminKpiCard label="Transfer Requested" value={kpis.transfer_requested || 0} accent="#7c3aed" icon="transit" iconBg="#f5f3ff" />
            <AdminKpiCard label="Leaving Notice" value={kpis.leaving_notice_submitted || 0} accent={T.error} icon="alert" iconBg={T.errorBg} />
            <AdminKpiCard label="Own Accommodation" value={kpis.own_accommodation || 0} accent="#2563eb" icon="user" iconBg="#eff6ff" />
            <AdminKpiCard label="No Update 7 Days" value={kpis.no_update_7_days || 0} accent="#8A5C00" icon="clock" iconBg="#FFF7E6" />
          </div>

          <div className="tab-bar">
            {VIEWS.map((item) => (
              <button
                key={item.key}
                className={`tab-item${view === item.key ? " active" : ""}`}
                onClick={() => setView(item.key)}
              >
                {item.label}
                <span className="tab-badge">{viewCounts[item.key] || 0}</span>
              </button>
            ))}
          </div>

          <Card style={{ marginBottom: 18 }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))",
                gap: 12,
              }}
            >
              <div style={{ gridColumn: "span 2", minWidth: 0 }}>
                <label className="f-label">Search</label>
                <input
                  className="f-input"
                  placeholder="Name, ref, passport, MTON, mobile, batch, vendor..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div>
                <label className="f-label">Vendor</label>
                <select className="f-input" value={vendor} onChange={(e) => setVendor(e.target.value)}>
                  <option value="">All vendors</option>
                  {(filterOptions.vendors || []).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="f-label">Facility</label>
                <select className="f-input" value={facility} onChange={(e) => setFacility(e.target.value)}>
                  <option value="">All facilities</option>
                  {(filterOptions.facilities || []).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="f-label">Status</label>
                <select className="f-input" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="">All statuses</option>
                  {(filterOptions.statuses || []).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="f-label">Accommodation Type</label>
                <select
                  className="f-input"
                  value={accommodationType}
                  onChange={(e) => setAccommodationType(e.target.value)}
                >
                  <option value="">All types</option>
                  {(filterOptions.accommodation_types || []).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="f-label">Preference</label>
                <select className="f-input" value={preference} onChange={(e) => setPreference(e.target.value)}>
                  <option value="">All preferences</option>
                  {(filterOptions.preferences || []).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="f-label">MTON</label>
                <input className="f-input" value={mton} onChange={(e) => setMton(e.target.value)} />
              </div>
              <div>
                <label className="f-label">No Update Days</label>
                <input
                  className="f-input"
                  type="number"
                  min={0}
                  value={noUpdateDays}
                  onChange={(e) => setNoUpdateDays(e.target.value)}
                />
              </div>
            </div>
            <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
              <Btn variant="navy" size="sm" icon="filter" onClick={() => void loadList()}>
                Apply Filters
              </Btn>
              <Btn
                variant="light"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setVendor("");
                  setFacility("");
                  setStatus("");
                  setAccommodationType("");
                  setPreference("");
                  setMton("");
                  setNoUpdateDays("");
                  void loadList({
                    search: "",
                    vendor: "",
                    facility: "",
                    status: "",
                    accommodation_type: "",
                    preference: "",
                    mton: "",
                    no_update_days: "",
                  });
                }}
              >
                Reset
              </Btn>
            </div>
          </Card>

          {accessDenied ? (
            <Card style={{ borderTop: `3px solid ${T.error}` }}>
              <div style={{ fontSize: 16, fontWeight: 800, color: T.error, marginBottom: 8 }}>
                Access denied
              </div>
              <p style={{ fontSize: 13, color: T.muted }}>
                Nurse vendor and accommodation tracking is restricted to the Nurses Welfare Desk and approved admin roles.
              </p>
            </Card>
          ) : (
            <Card pad={0}>
              <div style={{ padding: "16px 18px 0" }}>
                <div style={{ fontSize: 15, fontWeight: 800, color: T.navy }}>
                  {loading ? "Loading roster..." : `${visibleRows.length} records in this view`}
                </div>
                {error ? (
                  <p style={{ color: T.error, fontSize: 12, marginTop: 6 }}>{error}</p>
                ) : null}
              </div>
              <div style={{ overflowX: "auto", padding: 18 }}>
                <table className="a-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>MTON</th>
                      <th>Mobile</th>
                      <th>Batch</th>
                      <th>Current Accommodation</th>
                      <th>Vendor</th>
                      <th>Facility</th>
                      <th>Room / Bed</th>
                      <th>Contract Dates</th>
                      <th>Status</th>
                      <th>Leaving / Transfer</th>
                      <th>Last Updated</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!loading && visibleRows.length === 0 ? (
                      <tr>
                        <td colSpan={13} style={{ textAlign: "center", color: T.muted }}>
                          No records matched the selected filters.
                        </td>
                      </tr>
                    ) : null}
                    {visibleRows.map((row) => (
                      <tr key={`${row.nurse_id}-${row.roster_id || 0}`} onClick={() => void openDetail(row.nurse_id)}>
                        <td>
                          <div style={{ fontWeight: 700, color: T.navy }}>{row.name || "—"}</div>
                          <div style={{ fontSize: 11, color: T.muted }}>{row.nurse_reference || "—"}</div>
                        </td>
                        <td>{row.mton_number || "—"}</td>
                        <td>{row.mobile || "—"}</td>
                        <td>{row.batch || "—"}</td>
                        <td>{row.current_accommodation_type || "—"}</td>
                        <td>{row.vendor_name || "—"}</td>
                        <td>{row.facility_name || "—"}</td>
                        <td>{formatRoomBed(row)}</td>
                        <td>{formatDateRange(row.contract_start_date, row.contract_end_date)}</td>
                        <td>
                          <StatusBadge type={statusType(row.status)} label={row.status || "Unspecified"} />
                        </td>
                        <td>
                          <div>{row.leaving_notice_status || "—"}</div>
                          <div style={{ fontSize: 11, color: T.muted }}>
                            {row.transfer_requested ? "Transfer requested" : row.preference || "—"}
                          </div>
                        </td>
                        <td>
                          <div>{formatUpdated(row.last_updated)}</div>
                          <div style={{ fontSize: 11, color: T.muted }}>
                            {typeof row.no_update_days === "number" ? `${row.no_update_days} day(s)` : "—"}
                          </div>
                        </td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            <Btn variant="light" size="sm" icon="eye" onClick={() => void openDetail(row.nurse_id)}>
                              View
                            </Btn>
                            <Btn variant="light" size="sm" icon="home" onClick={() => void openDetail(row.nurse_id)}>
                              Update
                            </Btn>
                            <Btn
                              variant="light"
                              size="sm"
                              icon="note"
                              onClick={() => void copyMessage(row.nurse_id, "REQUEST_PREFERENCE")}
                            >
                              Copy message
                            </Btn>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      </div>

      {detailOpen ? (
        <>
          <div className="drawer-overlay" onClick={() => setDetailOpen(false)} />
          <div className="drawer-panel">
            <div style={{ padding: 22, borderBottom: `1px solid ${T.borderLt}`, position: "sticky", top: 0, background: T.surface, zIndex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: T.navy }}>
                    {detailData?.nurse?.full_name || "Accommodation detail"}
                  </div>
                  <div style={{ fontSize: 12, color: T.muted, marginTop: 4 }}>
                    {detailData?.nurse?.reference_id || "—"} • {detailData?.nurse?.mton_number || "No MTON"}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setDetailOpen(false)}
                  style={{
                    border: `1px solid ${T.borderLt}`,
                    background: T.surfaceLow,
                    borderRadius: 8,
                    width: 34,
                    height: 34,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Icon name="x" size={16} color={T.navy} />
                </button>
              </div>
            </div>

            <div style={{ padding: 22 }}>
              {detailLoading ? <p style={{ color: T.muted }}>Loading detail...</p> : null}
              {detailError ? <p style={{ color: T.error }}>{detailError}</p> : null}

              {detailData?.nurse ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <Card pad={18}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: T.navy, marginBottom: 12 }}>
                      Nurse identity
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 10, fontSize: 13 }}>
                      <div><strong>Reference:</strong> {detailData.nurse.reference_id || "—"}</div>
                      <div><strong>Father:</strong> {detailData.nurse.father_name || "—"}</div>
                      <div><strong>Passport:</strong> {detailData.nurse.passport_masked || "—"}</div>
                      <div><strong>Civil ID:</strong> {detailData.nurse.civil_id || "—"}</div>
                      <div><strong>Mobile:</strong> {detailData.nurse.mobile || "—"}</div>
                      <div><strong>WhatsApp:</strong> {detailData.nurse.whatsapp || "—"}</div>
                      <div><strong>Email:</strong> {detailData.nurse.email || "—"}</div>
                      <div><strong>Batch:</strong> {detailData.nurse.batch_number || "—"}</div>
                    </div>
                  </Card>

                  <Card pad={18}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: T.navy, marginBottom: 12 }}>
                      Current accommodation
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 10, fontSize: 13 }}>
                      <div><strong>Type:</strong> {detailData.summary?.current_accommodation_type || "—"}</div>
                      <div><strong>Status:</strong> {detailData.summary?.status || "—"}</div>
                      <div><strong>Vendor:</strong> {detailData.summary?.vendor_name || "—"}</div>
                      <div><strong>Facility:</strong> {detailData.summary?.facility_name || "—"}</div>
                      <div><strong>Room / Bed:</strong> {formatRoomBed(detailData.summary || { nurse_id: 0 })}</div>
                      <div><strong>Expected shift:</strong> {detailData.summary?.expected_shift_date || "—"}</div>
                      <div><strong>Contract:</strong> {formatDateRange(detailData.summary?.contract_start_date, detailData.summary?.contract_end_date)}</div>
                      <div><strong>Monthly rate:</strong> {detailData.summary?.monthly_rate == null || detailData.summary?.monthly_rate === "" ? "—" : String(detailData.summary?.monthly_rate)}</div>
                    </div>
                    <div style={{ marginTop: 12, fontSize: 13, color: T.muted }}>
                      <strong style={{ color: T.text }}>Notes:</strong> {detailData.summary?.notes || "—"}
                    </div>
                  </Card>

                  <Card pad={18}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: T.navy, marginBottom: 12 }}>
                      Update accommodation
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 12 }}>
                      <div>
                        <label className="f-label">Vendor</label>
                        <input className="f-input" value={form.vendor_name} onChange={(e) => setForm({ ...form, vendor_name: e.target.value })} />
                      </div>
                      <div>
                        <label className="f-label">Facility</label>
                        <input className="f-input" value={form.facility_name} onChange={(e) => setForm({ ...form, facility_name: e.target.value })} />
                      </div>
                      <div>
                        <label className="f-label">Room</label>
                        <input className="f-input" value={form.room_no} onChange={(e) => setForm({ ...form, room_no: e.target.value })} />
                      </div>
                      <div>
                        <label className="f-label">Bed</label>
                        <input className="f-input" value={form.bed_no} onChange={(e) => setForm({ ...form, bed_no: e.target.value })} />
                      </div>
                      <div>
                        <label className="f-label">Monthly Rate</label>
                        <input className="f-input" value={form.monthly_rate} onChange={(e) => setForm({ ...form, monthly_rate: e.target.value })} />
                      </div>
                      <div>
                        <label className="f-label">Status</label>
                        <input className="f-input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} />
                      </div>
                      <div>
                        <label className="f-label">Contract Start</label>
                        <input className="f-input" type="date" value={form.contract_start_date} onChange={(e) => setForm({ ...form, contract_start_date: e.target.value })} />
                      </div>
                      <div>
                        <label className="f-label">Contract End</label>
                        <input className="f-input" type="date" value={form.contract_end_date} onChange={(e) => setForm({ ...form, contract_end_date: e.target.value })} />
                      </div>
                      <div>
                        <label className="f-label">Expected Shift Date</label>
                        <input className="f-input" type="date" value={form.expected_shift_date} onChange={(e) => setForm({ ...form, expected_shift_date: e.target.value })} />
                      </div>
                      <div style={{ gridColumn: "span 2" }}>
                        <label className="f-label">Notes</label>
                        <textarea className="f-input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
                      <Btn variant="navy" size="sm" icon="check" onClick={() => void saveAccommodation()} disabled={saving}>
                        {saving ? "Saving..." : "Save accommodation"}
                      </Btn>
                      <Btn
                        variant="light"
                        size="sm"
                        icon="note"
                        onClick={() => {
                          const nurseId = detailData?.nurse?.id;
                          if (nurseId) void copyMessage(nurseId, "REQUEST_PREFERENCE");
                        }}
                      >
                        Copy preference message
                      </Btn>
                      <Btn
                        variant="light"
                        size="sm"
                        icon="note"
                        onClick={() => {
                          const nurseId = detailData?.nurse?.id;
                          if (nurseId) void copyMessage(nurseId, "SHIFT_NOTICE");
                        }}
                      >
                        Copy shift notice
                      </Btn>
                      <Btn
                        variant="light"
                        size="sm"
                        icon="note"
                        onClick={() => {
                          const nurseId = detailData?.nurse?.id;
                          if (nurseId) void copyMessage(nurseId, "TRANSFER_OPTION");
                        }}
                      >
                        Copy transfer option
                      </Btn>
                    </div>
                  </Card>

                  <Card pad={18}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: T.navy, marginBottom: 10 }}>
                      Recent actions
                    </div>
                    {detailData.actions?.length ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {detailData.actions.slice(0, 8).map((item) => (
                          <div key={item.id} style={{ borderBottom: `1px solid ${T.borderLt}`, paddingBottom: 10 }}>
                            <div style={{ fontSize: 13, fontWeight: 700, color: T.navy }}>
                              {item.action_type || "Update"}
                            </div>
                            <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>
                              {item.created_at || "—"} • {item.actor_username || "system"}
                            </div>
                            <div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>
                              {item.note || item.new_value || "—"}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: 13, color: T.muted }}>No recent roster actions.</p>
                    )}
                  </Card>

                  <Card pad={18}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: T.navy, marginBottom: 10 }}>
                      Leaving notices
                    </div>
                    {detailData.leave_notices?.length ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {detailData.leave_notices.slice(0, 6).map((item) => (
                          <div key={String(item.id)} style={{ fontSize: 13 }}>
                            <strong>{item.notice_status || "Submitted"}</strong> • {item.intended_leaving_date || "No date"}
                            <div style={{ color: T.muted, marginTop: 2 }}>{item.reason || item.new_stay_arrangement || "—"}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: 13, color: T.muted }}>No leaving notices on file.</p>
                    )}
                  </Card>

                  <Card pad={18}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: T.navy, marginBottom: 10 }}>
                      Accommodation requests
                    </div>
                    {detailData.accommodation_requests?.length ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {detailData.accommodation_requests.slice(0, 6).map((item) => (
                          <div key={String(item.id)} style={{ fontSize: 13 }}>
                            <strong>{item.request_status || "Pending"}</strong> • {item.requested_facility || item.current_accommodation_status || "—"}
                            <div style={{ color: T.muted, marginTop: 2 }}>{item.reason_remarks || item.admin_remarks || "—"}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: 13, color: T.muted }}>No accommodation requests on file.</p>
                    )}
                  </Card>
                </div>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </AdminLayout>
  );
}
