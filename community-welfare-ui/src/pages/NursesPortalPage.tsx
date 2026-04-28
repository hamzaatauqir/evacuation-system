import { type ReactNode, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PublicHeader } from "../components/PublicHeader";
import { PageFooter } from "../components/PageFooter";
import { Btn } from "../components/Btn";
import { StatusBadge } from "../components/StatusBadge";
import { api } from "../lib/api";
import { addLocalPortalRequest, clearNursePortal, getLocalPortalRequests, getNursePortal } from "../lib/nursePortal";

export function NursesPortalPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [ctx] = useState(() => getNursePortal());
  const requests = useMemo(() => getLocalPortalRequests(), []);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [facilityReq, setFacilityReq] = useState({ current_stay_arrangement: "", requested_facility: "", reason_remarks: "" });
  const [stay, setStay] = useState(() => ({
    confirmation_option: "",
    current_facility_name: ctx?.facilityRoster?.facility_name || "",
    area: ctx?.facilityRoster?.area || "",
    room_number: ctx?.facilityRoster?.room_number || "",
    bed_number: ctx?.facilityRoster?.bed_number || "",
    current_phone: ctx?.mobile || "",
    preferred_contact_method: "WhatsApp",
    remarks: "",
  }));
  const [complaint, setComplaint] = useState({ complaint_category: "", priority: "Normal", subject: "", description: "" });
  const [leaving, setLeaving] = useState({ current_facility: "", intended_leaving_date: "", reason: "" });
  const [curPwd, setCurPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmNew, setConfirmNew] = useState("");
  const [showPw, setShowPw] = useState(false);

  if (!ctx) {
    navigate("/nurses/login", { replace: true });
    return null;
  }

  const tab = params.get("tab") || "overview";
  const tabs = ["overview", "stay", "complaint", "leaving", "requests", "password"];
  const activeTab = tabs.includes(tab) ? tab : "overview";

  const statusType = (ctx.registrationStatus || "").toLowerCase().includes("resolved")
    ? "resolved"
    : (ctx.registrationStatus || "").toLowerCase().includes("progress")
    ? "processing"
    : "pending";

  async function submitFacilityRequest() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/accommodation", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        current_accommodation_status: facilityReq.current_stay_arrangement,
        requested_facility: facilityReq.requested_facility,
        reason_remarks: facilityReq.reason_remarks,
      });
      addLocalPortalRequest({ type: "Facility Assistance", summary: `Type: ${facilityReq.requested_facility || "N/A"}` });
      setMsg("Facility assistance request submitted. Marked as pending official review.");
      setFacilityReq({ current_stay_arrangement: "", requested_facility: "", reason_remarks: "" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit facility assistance request.");
    } finally {
      setBusy(false);
    }
  }

  async function submitStayConfirmation() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/stay-confirmation", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        ...stay,
      });
      addLocalPortalRequest({ type: "Stay Confirmation", summary: "Stay arrangement update submitted." });
      setMsg("Stay arrangement confirmation submitted for Community Welfare Wing review.");
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit stay arrangement confirmation.");
    } finally {
      setBusy(false);
    }
  }

  async function submitComplaint() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/complaint", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        complaint_category: complaint.complaint_category,
        priority: complaint.priority,
        subject: complaint.subject,
        description: complaint.description,
        preferred_contact_method: "WhatsApp",
        consent: true,
      });
      addLocalPortalRequest({ type: "Complaint", summary: `Subject: ${complaint.subject || "N/A"}` });
      setMsg("Complaint submitted. Marked as pending official review.");
      setComplaint({ complaint_category: "", priority: "Normal", subject: "", description: "" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit complaint.");
    } finally {
      setBusy(false);
    }
  }

  async function submitLeavingNotice() {
    setBusy(true); setErr(""); setMsg("");
    try {
      await api.post("/api/nurses/leave-notice", {
        nurse_reference_id: ctx.referenceId,
        passport_number: ctx.passportNumber,
        verifier: ctx.mobile || ctx.civilId || "",
        current_facility: leaving.current_facility,
        intended_leaving_date: leaving.intended_leaving_date,
        reason: leaving.reason,
      });
      addLocalPortalRequest({ type: "Leaving Notice", summary: `Move out date: ${leaving.intended_leaving_date || "N/A"}` });
      setMsg("Leaving notice submitted. Marked as pending official review.");
      setLeaving({ current_facility: "", intended_leaving_date: "", reason: "" });
      setParams({ tab: "requests" });
    } catch (e) {
      setErr((e as Error).message || "Could not submit leaving notice.");
    } finally {
      setBusy(false);
    }
  }

  async function submitChangePassword() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.post("/api/nurses/change-password", {
        nurse_reference_id: ctx.referenceId,
        current_password: curPwd,
        new_password: newPwd,
        confirm_password: confirmNew,
      });
      setMsg("Password updated.");
      setCurPwd("");
      setNewPwd("");
      setConfirmNew("");
    } catch (e) {
      setErr((e as Error).message || "Could not change password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fade-in" style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <PublicHeader />
      <main style={{ flex: 1, maxWidth: 1120, margin: "0 auto", width: "100%", padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ fontSize: 28, color: "#2D4A6B" }}>Welcome, {ctx.fullName || "Nurse"}</h1>
          <Btn
            variant="light"
            onClick={() => {
              clearNursePortal();
              navigate("/nurses/login");
            }}
          >
            Logout / Clear Portal Session
          </Btn>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
          {tabs.map((t) => (
            <Btn key={t} variant={activeTab === t ? "navy" : "light"} onClick={() => setParams({ tab: t })}>
              {t === "overview"
                ? "Overview"
                : t === "stay"
                  ? "Stay Arrangement"
                  : t === "complaint"
                    ? "Complaint"
                    : t === "leaving"
                      ? "Leaving Notice"
                      : t === "requests"
                        ? "My Requests"
                        : "Change password"}
            </Btn>
          ))}
        </div>

        {(msg || err) ? (
          <div style={{ marginBottom: 14, background: err ? "#fff4f4" : "#f3fff4", color: err ? "#991b1b" : "#166534", border: `1px solid ${err ? "#fecaca" : "#bbf7d0"}`, borderRadius: 10, padding: 10 }}>
            {err || msg}
          </div>
        ) : null}

        {activeTab === "overview" ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 14, marginBottom: 14 }}>
              <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16 }}>
                <h3 style={{ marginBottom: 10, color: "#2D4A6B" }}>Nurse Profile Summary</h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <Field label="Reference ID" value={ctx.referenceId || "-"} />
                  <Field label="Name" value={ctx.fullName || "-"} />
                  <Field label="Email" value={ctx.email || "-"} />
                  <Field label="Passport" value={ctx.passportMasked || "-"} />
                  <Field label="Civil ID (if any)" value={ctx.civilIdMasked || "—"} />
                  <Field label="Status" value={ctx.registrationStatus || "-"} />
                  <Field label="Last Updated" value={ctx.lastUpdated || "-"} />
                  <Field label="Current Stay Arrangement" value={ctx.facilityRoster?.current_status || "Not linked to a facility record"} />
                  <Field label="Facility" value={ctx.facilityRoster?.facility_name || "—"} />
                </div>
              </div>
              <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16 }}>
                <h3 style={{ marginBottom: 10, color: "#2D4A6B" }}>Tracking / Status</h3>
                <div style={{ marginBottom: 8 }}><StatusBadge type={statusType as any} label={ctx.registrationStatus || "Pending"} /></div>
                <p style={{ color: "#5B6773", fontSize: 13, marginTop: 8 }}><strong>Embassy remarks:</strong> {ctx.remarks || "No remarks yet."}</p>
                <p style={{ color: "#5B6773", fontSize: 13, marginTop: 8 }}><strong>What you should do now:</strong> Keep tracking this portal for review updates and follow any Embassy remarks.</p>
              </div>
            </div>
            <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16 }}>
              <h3 style={{ marginBottom: 8, color: "#2D4A6B" }}>Embassy Messages</h3>
              <p style={{ color: "#5B6773" }}>{ctx.remarks || "Embassy messages and remarks will appear here after review."}</p>
            </div>
          </>
        ) : null}

        {activeTab === "stay" ? (
          <div style={{ display: "grid", gap: 14 }}>
            {ctx.facilityRoster ? (
              <FormCard title="Stay Arrangement Confirmation">
                <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                  Our records show that you may be assigned to an Embassy-arranged or Embassy-contracted
                  facility. Please confirm your current stay arrangement so the Community Welfare Wing can
                  maintain accurate welfare records and provide timely assistance where required.
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
                  <Field label="Roster Reference" value={ctx.facilityRoster.roster_reference || "-"} />
                  <Field label="Facility" value={ctx.facilityRoster.facility_name || "-"} />
                  <Field label="Vendor" value={ctx.facilityRoster.vendor_name || "-"} />
                  <Field label="Notice Period Start" value={ctx.facilityRoster.notice_period_start_date || "-"} />
                </div>
                <label>
                  Confirmation option
                  <select className="f-input" value={stay.confirmation_option} onChange={(e) => setStay({ ...stay, confirmation_option: e.target.value })}>
                    <option value="">Select</option>
                    <option value="currently_staying">I am currently staying at this facility</option>
                    <option value="shifted_from_facility">I have shifted from this facility</option>
                    <option value="intends_to_leave">I intend to leave/change my stay arrangement</option>
                    <option value="details_correction">My facility details require correction</option>
                    <option value="assistance_requested">I need welfare assistance/follow-up</option>
                  </select>
                </label>
                <label>Current facility name<input className="f-input" value={stay.current_facility_name} onChange={(e) => setStay({ ...stay, current_facility_name: e.target.value })} /></label>
                <label>Area<input className="f-input" value={stay.area} onChange={(e) => setStay({ ...stay, area: e.target.value })} /></label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <label>Room<input className="f-input" value={stay.room_number} onChange={(e) => setStay({ ...stay, room_number: e.target.value })} /></label>
                  <label>Bed<input className="f-input" value={stay.bed_number} onChange={(e) => setStay({ ...stay, bed_number: e.target.value })} /></label>
                </div>
                <label>Current phone / WhatsApp<input className="f-input" value={stay.current_phone} onChange={(e) => setStay({ ...stay, current_phone: e.target.value })} /></label>
                <label>
                  Preferred contact method
                  <select className="f-input" value={stay.preferred_contact_method} onChange={(e) => setStay({ ...stay, preferred_contact_method: e.target.value })}>
                    <option>WhatsApp</option>
                    <option>Phone Call</option>
                    <option>Email</option>
                  </select>
                </label>
                <label>Remarks<textarea className="f-input" value={stay.remarks} onChange={(e) => setStay({ ...stay, remarks: e.target.value })} /></label>
                <Btn variant="primary" disabled={busy || !stay.confirmation_option} onClick={submitStayConfirmation}>{busy ? "Submitting..." : "Submit Stay Confirmation"}</Btn>
              </FormCard>
            ) : (
              <FormCard title="Stay Arrangement Confirmation">
                <p style={{ color: "#5B6773", fontSize: 13, lineHeight: 1.6 }}>
                  No Embassy-arranged or Embassy-contracted facility record is currently linked to your profile.
                  You may still submit a facility assistance request if you need Community Welfare Wing follow-up.
                </p>
              </FormCard>
            )}
            <FormCard title="Facility Assistance Request">
              <label>Current Stay Arrangement<input className="f-input" value={facilityReq.current_stay_arrangement} onChange={(e) => setFacilityReq({ ...facilityReq, current_stay_arrangement: e.target.value })} /></label>
              <label>Requested Facility Assistance<input className="f-input" value={facilityReq.requested_facility} onChange={(e) => setFacilityReq({ ...facilityReq, requested_facility: e.target.value })} /></label>
              <label>Reason / Remarks<textarea className="f-input" value={facilityReq.reason_remarks} onChange={(e) => setFacilityReq({ ...facilityReq, reason_remarks: e.target.value })} /></label>
              <Btn variant="primary" disabled={busy} onClick={submitFacilityRequest}>{busy ? "Submitting..." : "Submit Facility Assistance Request"}</Btn>
            </FormCard>
          </div>
        ) : null}

        {activeTab === "complaint" ? (
          <FormCard title="Complaint / Welfare Issue">
            <label>Category<input className="f-input" value={complaint.complaint_category} onChange={(e) => setComplaint({ ...complaint, complaint_category: e.target.value })} /></label>
            <label>Priority<select className="f-input" value={complaint.priority} onChange={(e) => setComplaint({ ...complaint, priority: e.target.value })}><option>Normal</option><option>Important</option><option>Urgent</option></select></label>
            <label>Subject<input className="f-input" value={complaint.subject} onChange={(e) => setComplaint({ ...complaint, subject: e.target.value })} /></label>
            <label>Details<textarea className="f-input" value={complaint.description} onChange={(e) => setComplaint({ ...complaint, description: e.target.value })} /></label>
            <Btn variant="primary" disabled={busy} onClick={submitComplaint}>{busy ? "Submitting..." : "Submit Complaint"}</Btn>
          </FormCard>
        ) : null}

        {activeTab === "leaving" ? (
          <FormCard title="Leaving Notice / Exit">
            <label>Current Facility<input className="f-input" value={leaving.current_facility} onChange={(e) => setLeaving({ ...leaving, current_facility: e.target.value })} /></label>
            <label>Expected Move Out Date<input className="f-input" type="date" value={leaving.intended_leaving_date} onChange={(e) => setLeaving({ ...leaving, intended_leaving_date: e.target.value })} /></label>
            <label>Reason<textarea className="f-input" value={leaving.reason} onChange={(e) => setLeaving({ ...leaving, reason: e.target.value })} /></label>
            <Btn variant="primary" disabled={busy} onClick={submitLeavingNotice}>{busy ? "Submitting..." : "Submit Leaving Notice"}</Btn>
          </FormCard>
        ) : null}

        {activeTab === "password" ? (
          <FormCard title="Change password">
            <label>
              Current password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={curPwd}
                onChange={(e) => setCurPwd(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            <label>
              New password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <label>
              Confirm new password
              <input
                className="f-input"
                type={showPw ? "text" : "password"}
                value={confirmNew}
                onChange={(e) => setConfirmNew(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <button
              type="button"
              className="f-input"
              style={{ width: "auto", cursor: "pointer", maxWidth: 120 }}
              onClick={() => setShowPw((s) => !s)}
            >
              {showPw ? "Hide passwords" : "Show passwords"}
            </button>
            <Btn variant="primary" disabled={busy} onClick={submitChangePassword}>
              {busy ? "Updating…" : "Update password"}
            </Btn>
          </FormCard>
        ) : null}

        {activeTab === "requests" ? (
          <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16, marginBottom: 14 }}>
            <h3 style={{ marginBottom: 12, color: "#2D4A6B" }}>My Requests / History</h3>
            {ctx.complaints?.length ? (
              <div style={{ display: "grid", gap: 8, marginBottom: 10 }}>
                {ctx.complaints.slice(0, 10).map((c, idx) => (
                  <div key={c.complaint_id || idx} style={{ border: "1px solid #E3EBF0", borderRadius: 10, padding: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <strong>{c.subject || "Complaint"}</strong>
                      <StatusBadge type={(c.status || "").toLowerCase().includes("resolved") ? "resolved" : "processing"} label={c.status || "In Review"} />
                    </div>
                    <p style={{ fontSize: 12, color: "#5B6773" }}>Type: {c.category || "-"} | Submitted: {c.submitted_date || "-"}</p>
                  </div>
                ))}
              </div>
            ) : null}
            {requests.length ? (
              <div style={{ display: "grid", gap: 8 }}>
                {requests.map((r) => (
                  <div key={r.id} style={{ border: "1px dashed #D8E0E7", borderRadius: 10, padding: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                      <strong>{r.type}</strong>
                      <StatusBadge type="pending" label={`${r.status} (pending official review)`} />
                    </div>
                    <p style={{ fontSize: 12, color: "#5B6773" }}>{r.summary}</p>
                    <p style={{ fontSize: 11, color: "#7A8A96" }}>{r.submittedAt}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: "#5B6773" }}>Submitted requests will appear here once processed by the Embassy.</p>
            )}
          </div>
        ) : null}
      </main>
      <PageFooter />
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return <div><div style={{ fontSize: 11, color: '#7A8A96', marginBottom: 2 }}>{label}</div><div style={{ fontSize: 13, fontWeight: 600 }}>{value}</div></div>;
}

function FormCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #E3EBF0", padding: 16, display: "grid", gap: 10 }}>
      <h3 style={{ color: "#2D4A6B" }}>{title}</h3>
      {children}
    </div>
  );
}
